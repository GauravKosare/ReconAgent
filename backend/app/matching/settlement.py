"""Settlement-batch reconciliation — for real bank data where one bank credit
covers a whole PG settlement batch (and Route splits it into several).

Two-level match:
  1. PG batch  <->  bank payout(s)   — grouped by settlement_utr, sums compared
     (handles aggregation and Route splits).
  2. within a reconciled batch, each PG line  <->  ledger row  — joined on the
     order id / receipt.

Anything that does not tie out cleanly is returned as a leftover for the
deterministic signals + agent stages (FEE_MISMATCH, MISSING_IN_LEDGER,
MISSING_PAYOUT, TIMING_GAP, SHORT_SETTLEMENT, SPLIT_PAYOUT).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from ..models import MatchGroup, MatchMethod, NormalizedTxn, Source

AMOUNT_TOL_INR = 2.0
BATCH_REL_TOL = 0.002          # 0.2% slack for rounding across a batch
FEE_TOL_INR = 1.0

# Contracted MDR by method (percent of gross) + a flat per-txn fee. These are
# the merchant's agreed rates; a PG line that deviates is a FEE_MISMATCH.
MDR_BY_METHOD = {
    "upi": (0.0, 0.0),
    "card": (1.9, 0.0),
    "wallet": (1.7, 0.0),
    "netbanking": (0.0, 12.0),
}
GST_ON_FEE = 0.18


@dataclass
class BatchOutcome:
    settlement_id: str
    settlement_utr: str | None
    pg_lines: list[NormalizedTxn]
    bank_rows: list[NormalizedTxn]
    expected_payout: float
    actual_payout: float
    reconciled: bool
    reason: str


@dataclass
class LineIssue:
    pg: NormalizedTxn
    ledger: NormalizedTxn | None
    code: str
    impact: float
    detail: str


@dataclass
class SettlementResult:
    groups: list[MatchGroup]
    leftovers: list[NormalizedTxn]
    batches: list[BatchOutcome]
    line_issues: list[LineIssue] = field(default_factory=list)

    @property
    def batch_report(self) -> dict:
        return {
            "batches": len(self.batches),
            "reconciled": sum(1 for b in self.batches if b.reconciled),
            "unreconciled": sum(1 for b in self.batches if not b.reconciled),
            "auto_matched_lines": len(self.groups),
        }


def _key(t: NormalizedTxn) -> str | None:
    return (t.utr or "").upper() or None


def _ledger_index(ledger: list[NormalizedTxn]) -> dict[str, NormalizedTxn]:
    idx: dict[str, NormalizedTxn] = {}
    for le in ledger:
        for k in filter(None, (le.external_id, le.narration)):
            idx.setdefault(str(k).upper(), le)
    return idx


def _find_ledger(pg: NormalizedTxn, idx: dict[str, NormalizedTxn]) -> NormalizedTxn | None:
    for k in filter(None, (pg.external_id,)):
        hit = idx.get(str(k).upper())
        if hit and abs(hit.amount_gross - pg.amount_gross) <= AMOUNT_TOL_INR:
            return hit
    # receipt token appears inside another id
    for k, le in idx.items():
        if pg.external_id and pg.external_id.upper() in k and abs(le.amount_gross - pg.amount_gross) <= AMOUNT_TOL_INR:
            return le
    return None


def reconcile_settlements(
    txns: list[NormalizedTxn],
    *,
    sla_days: int = 2,
    mdr_percent: float = 2.0,
    gst_percent: float = 18.0,
    tds_percent: float = 0.0,        # 194-O TDS withheld from marketplace payouts
    reserve_percent: float = 0.0,    # rolling reserve held from each payout
) -> SettlementResult:
    by_src: dict[Source, list[NormalizedTxn]] = defaultdict(list)
    for t in txns:
        by_src[t.source].append(t)

    ledger_idx = _ledger_index(by_src[Source.LEDGER])
    used_ledger: set[str] = set()

    # group PG lines into settlement batches
    pg_batches: dict[str, list[NormalizedTxn]] = defaultdict(list)
    for pg in by_src[Source.PG]:
        pg_batches[pg.settlement_id or _key(pg) or pg.raw_record_id].append(pg)

    # index bank rows by settlement utr
    bank_by_utr: dict[str, list[NormalizedTxn]] = defaultdict(list)
    for b in by_src[Source.BANK]:
        if _key(b):
            bank_by_utr[_key(b)].append(b)
    bank_unclaimed = list(by_src[Source.BANK])

    groups: list[MatchGroup] = []
    leftovers: list[NormalizedTxn] = []
    outcomes: list[BatchOutcome] = []
    line_issues: list[LineIssue] = []

    for sid, lines in pg_batches.items():
        batch_utr = next((_key(x) for x in lines if _key(x)), None)
        payments = [x for x in lines if x.kind != "refund"]
        gross_net = round(sum(x.amount_net for x in lines), 2)
        # marketplace payouts arrive net of TDS + rolling reserve — a known,
        # contracted deduction, not a discrepancy.
        tds = round(sum(x.amount_gross for x in payments) * tds_percent / 100.0, 2)
        reserve = round(gross_net * reserve_percent / 100.0, 2)
        expected = round(gross_net - tds - reserve, 2)

        bank_rows = bank_by_utr.get(batch_utr, []) if batch_utr else []
        if not bank_rows:
            bank_rows = _fuzzy_bank(lines, bank_unclaimed, expected, sla_days)
        actual = round(sum(b.amount_net for b in bank_rows), 2)

        within_sla = _within_sla(lines, bank_rows, sla_days)
        tol = max(AMOUNT_TOL_INR, abs(expected) * BATCH_REL_TOL) + (0.5 if tds or reserve else 0.0)
        reconciled = bool(bank_rows) and abs(expected - actual) <= tol and within_sla

        if reconciled:
            for b in bank_rows:
                if b in bank_unclaimed:
                    bank_unclaimed.remove(b)

        reason = (
            "batch payout reconciled"
            if reconciled
            else "no bank payout" if not bank_rows
            else "payout late" if not within_sla
            else f"payout off by {round(actual - expected, 2)}"
        )
        outcomes.append(
            BatchOutcome(sid, batch_utr, lines, bank_rows, expected, actual, reconciled, reason)
        )

        anchor_bank = bank_rows[0].raw_record_id if bank_rows else None
        gross_seen: dict[str, int] = defaultdict(int)
        for pg in payments:
            led = _find_ledger(pg, ledger_idx)
            pct, flat = MDR_BY_METHOD.get(pg.method or "", (mdr_percent, 0.0))
            is_intl = pg.currency not in ("INR", "", None) or "international" in (pg.narration or "").lower()
            # on international cards Razorpay folds a ~3.5% forex + cross-border
            # fee into `fee`; allow for it before calling a fee mismatch
            intl_slack = round(pg.amount_gross * 0.045, 2) if is_intl else 0.0
            expected_fee = round(pg.amount_gross * pct / 100.0 + flat, 2)
            expected_tax = round(expected_fee * GST_ON_FEE, 2)
            expected_net = round(pg.amount_gross - expected_fee - expected_tax, 2)
            fee_delta = round(pg.fee - expected_fee, 2)
            net_short = round(expected_net - pg.amount_net, 2)

            if not reconciled:
                # batch-level problem — handled by BatchOutcome, don't double-count
                if led is not None and led.raw_record_id not in used_ledger:
                    used_ledger.add(led.raw_record_id)
                continue

            if led is None:
                line_issues.append(LineIssue(pg, None, "MISSING_IN_LEDGER", pg.amount_net,
                                             "money received, no matching ledger row"))
            elif fee_delta > FEE_TOL_INR + intl_slack:
                used_ledger.add(led.raw_record_id)
                line_issues.append(LineIssue(pg, led, "FEE_MISMATCH", net_short,
                                             f"PG fee {pg.fee} vs contracted {expected_fee}"))
            elif net_short > AMOUNT_TOL_INR + intl_slack:
                used_ledger.add(led.raw_record_id)
                line_issues.append(LineIssue(pg, led, "SHORT_SETTLEMENT", round(net_short - intl_slack, 2),
                                             f"net {pg.amount_net} vs expected {expected_net}, fee is correct"))
            else:
                used_ledger.add(led.raw_record_id)
                gross_seen[f"{led.external_id}:{round(led.amount_gross, 2)}"] += 1
                groups.append(
                    MatchGroup(
                        batch_id=pg.batch_id, status="auto_matched", method=MatchMethod.EXACT,
                        ledger_txn_id=led.raw_record_id, pg_txn_id=pg.raw_record_id,
                        bank_txn_id=anchor_bank, note=f"settlement:{sid}",
                    )
                )

    # duplicate ledger rows (webhook double-fire): same external_id + gross twice
    led_seen: dict[str, list[NormalizedTxn]] = defaultdict(list)
    for le in by_src[Source.LEDGER]:
        led_seen[f"{le.external_id}:{round(le.amount_gross, 2)}"].append(le)
    for key, rows in led_seen.items():
        if len(rows) > 1:
            for dup in rows[1:]:
                line_issues.append(LineIssue(dup, dup, "DUPLICATE", dup.amount_gross,
                                             f"ledger row {key} appears {len(rows)} times"))

    leftovers.extend(bank_unclaimed)
    return SettlementResult(groups, leftovers, outcomes, line_issues)


def _within_sla(pg_lines, bank_rows, sla_days: int) -> bool:
    if not bank_rows:
        return False
    settled = [x.settlement_date or x.txn_date for x in pg_lines if (x.settlement_date or x.txn_date)]
    credited = [b.settlement_date or b.txn_date for b in bank_rows if (b.settlement_date or b.txn_date)]
    if not settled or not credited:
        return True
    return (max(credited) - min(settled)).days <= sla_days + 1


def _fuzzy_bank(pg_lines, pool, expected, sla_days: int) -> list[NormalizedTxn]:
    """Last resort when the bank rows carry no clean UTR (e.g. terse RTGS)."""
    settled = [x.settlement_date or x.txn_date for x in pg_lines if (x.settlement_date or x.txn_date)]
    if not settled:
        return []
    win_lo, win_hi = min(settled) - timedelta(days=1), max(settled) + timedelta(days=sla_days + 3)
    cands = [
        b for b in pool
        if b.amount_net > 0
        and (b.settlement_date or b.txn_date)
        and win_lo <= (b.settlement_date or b.txn_date) <= win_hi
        and abs(b.amount_net - expected) <= max(AMOUNT_TOL_INR, abs(expected) * BATCH_REL_TOL)
    ]
    return cands[:1]

"""Deterministic pre-classification of an unresolved cluster.

This is the heart of the accuracy story: Python computes hard, explainable
signals from the cluster (which sources are present, do amounts agree, is the
fee correct, did the bank credit arrive late, is it a duplicate) and derives a
`suggested_code`. The LLM then only *adjudicates* that suggestion — confirm it,
or override with a named reason. That keeps classification accuracy close to the
accuracy of these rules rather than the accuracy of a small free model.

When no LLM is available the pipeline uses `suggested_code` directly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from ..models import Source
from .candidates import Cluster
from .fees import recompute_expected_fee

AMOUNT_TOL_INR = 1.0
FEE_TOL_INR = 0.5


@dataclass
class Signals:
    anchor_source: str
    sources_in_cluster: list[str]
    ledger_present: bool
    pg_present: bool
    bank_present: bool

    best_candidate_id: str | None
    amounts_agree: bool
    anchor_amount: float
    best_candidate_amount: float | None

    fee_overcharge_inr: float          # pg fee - contracted fee  (>0 = overcharged)
    net_short_inr: float               # expected net - actual net (>0 = merchant short-paid)
    bank_late_days: int | None         # bank value date - pg settlement date
    sla_days: int
    sla_breached: bool
    is_duplicate: bool
    duplicate_of: list[str]

    suggested_verdict: str             # matched | exception | unexplained
    suggested_code: str | None         # ExceptionCode value, or None
    suggested_amount_impact: float
    suggested_direction: str
    reason: str                        # which rule fired

    def as_dict(self) -> dict:
        return asdict(self)


def _amt(t) -> float:
    return t.amount_net or t.amount_gross


def _same_txn(a, b) -> bool:
    """True if two rows plausibly refer to the same transaction: a UTR/RRN match
    when both carry one, otherwise fall back to the caller's amount check."""
    if a.utr and b.utr:
        return a.utr.upper() == b.utr.upper()
    return True  # let the amount test decide


def compute_signals(
    cluster: Cluster,
    same_source_rows: list,
    *,
    mdr_percent: float,
    gst_percent: float,
    sla_days: int,
    ref_date: datetime | None,
) -> Signals:
    anchor = cluster.anchor
    cands = [c.txn for c in cluster.candidates]
    srcs = {anchor.source, *(c.source for c in cands)}

    ledger_present = Source.LEDGER in srcs
    pg_present = Source.PG in srcs
    bank_present = Source.BANK in srcs

    # The PG settlement row is the hub: ledger.gross ~ pg.gross, bank.net ~ pg.net.
    pg_cands = [c for c in cands if c.source is Source.PG]
    pg_row = (
        anchor
        if anchor.source is Source.PG
        else next((c for c in pg_cands if _same_txn(anchor, c)), None)
        or (pg_cands[0] if pg_cands else None)
    )
    # A ledger candidate only counts if its gross matches the PG gross (or the
    # anchor amount when there is no PG row) — a stray ledger row nearby doesn't.
    target_gross = pg_row.amount_gross if pg_row else anchor.amount_gross
    ledger_candidates = [c for c in cands if c.source is Source.LEDGER] + (
        [anchor] if anchor.source is Source.LEDGER else []
    )
    ledger_row = next(
        (
            le
            for le in ledger_candidates
            if _same_txn(anchor, le) and abs(le.amount_gross - target_gross) <= AMOUNT_TOL_INR
        ),
        None,
    )
    ledger_matched = ledger_row is not None

    fee_overcharge = 0.0
    net_short = 0.0
    if pg_row is not None:
        fe = recompute_expected_fee(pg_row, mdr_percent, gst_percent, FEE_TOL_INR)
        fee_overcharge = round(fe.fee_delta, 2)     # actual - expected
        net_short = round(fe.net_delta, 2)          # expected - actual

    # A bank candidate only counts as "the payout" if its amount matches the PG
    # net (or, with no PG row, the anchor amount). A random look-alike bank row
    # in the candidate list does NOT count.
    target_net = (pg_row.amount_net if pg_row else _amt(anchor))
    bank_candidates = [
        c for c in cands if c.source is Source.BANK
    ] + ([anchor] if anchor.source is Source.BANK else [])
    bank_row = next(
        (
            b
            for b in bank_candidates
            if _same_txn(anchor, b) and abs(_amt(b) - target_net) <= AMOUNT_TOL_INR
        ),
        None,
    )
    bank_matched = bank_row is not None
    bank_present = bool(bank_candidates)

    best = bank_row or pg_row or (cands[0] if cands else None)
    amounts_agree = bank_matched or ledger_matched

    bank_late_days: int | None = None
    if bank_row is not None and pg_row is not None:
        pgd = pg_row.settlement_date or pg_row.txn_date
        bkd = bank_row.settlement_date or bank_row.txn_date
        if pgd and bkd:
            bank_late_days = (bkd - pgd).days

    base = (pg_row.settlement_date if pg_row else None) or anchor.settlement_date or anchor.txn_date
    sla_breached = bool(base and ref_date and (ref_date - base).days > sla_days)

    dupes = [
        r.raw_record_id
        for r in same_source_rows
        if r.raw_record_id != anchor.raw_record_id
        and r.utr
        and anchor.utr
        and r.utr == anchor.utr
        and abs(r.amount_gross - anchor.amount_gross) < 0.01
    ]
    is_duplicate = bool(dupes)

    # -------- deterministic decision (first rule that fires wins) --------
    verdict, code, impact, direction, reason = "exception", None, 0.0, "neutral", ""
    anchor_net = _amt(anchor)

    if is_duplicate:
        code, impact, reason = "DUPLICATE", anchor_net, "same utr+amount twice in one source"
    elif anchor.source in (Source.PG, Source.BANK) and not ledger_matched:
        code, impact, reason = "MISSING_IN_LEDGER", anchor_net, "money received, no matching ledger row"
        direction = "merchant_owed"
    elif fee_overcharge > FEE_TOL_INR:
        code, impact, reason = "FEE_MISMATCH", net_short, f"PG fee over contract by {fee_overcharge}"
        direction = "merchant_owed"
    elif net_short > AMOUNT_TOL_INR:
        code, impact, reason = "SHORT_SETTLEMENT", net_short, f"net short by {net_short}, fee is correct"
        direction = "merchant_owed"
    elif not bank_matched and sla_breached:
        code, impact, reason = "MISSING_PAYOUT", anchor_net, "PG settled, no matching bank credit, SLA breached"
        direction = "merchant_owed"
    elif not bank_matched and not sla_breached:
        code, impact, reason = "TIMING_GAP", anchor_net, "bank credit not in yet, still within SLA"
    elif bank_matched and bank_late_days is not None and bank_late_days > sla_days:
        code, impact, reason = "TIMING_GAP", anchor_net, f"bank credit {bank_late_days}d after settlement"
    elif ledger_matched and bank_matched:
        verdict, reason = "matched", "ledger, PG and bank agree on amount and timing"
    else:
        verdict, code, reason = "unexplained", None, "no deterministic rule fits"

    return Signals(
        anchor_source=anchor.source.value,
        sources_in_cluster=sorted(s.value for s in srcs),
        ledger_present=ledger_present,
        pg_present=pg_present,
        bank_present=bank_present,
        best_candidate_id=best.raw_record_id if best else None,
        amounts_agree=amounts_agree,
        anchor_amount=round(_amt(anchor), 2),
        best_candidate_amount=round(_amt(best), 2) if best else None,
        fee_overcharge_inr=fee_overcharge,
        net_short_inr=net_short,
        bank_late_days=bank_late_days,
        sla_days=sla_days,
        sla_breached=sla_breached,
        is_duplicate=is_duplicate,
        duplicate_of=dupes,
        suggested_verdict=verdict,
        suggested_code=code,
        suggested_amount_impact=round(float(impact), 2),
        suggested_direction=direction,
        reason=reason,
    )

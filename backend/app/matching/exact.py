"""Stage 1 — deterministic three-way exact match. No LLM involved.

Strategy: join on the strongest available key (UTR/RRN), then fall back to
(external_id) and finally to (rounded amount + date window). A group is
"auto_matched" only when ledger + pg + bank all tie out within tolerance.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from ..models import MatchGroup, MatchMethod, NormalizedTxn, Source

AMOUNT_TOLERANCE_INR = 1.0


def _key_utr(t: NormalizedTxn) -> str | None:
    return t.utr.upper() if t.utr else None


def _within_window(a: NormalizedTxn, b: NormalizedTxn, sla_days: int) -> bool:
    da = a.settlement_date or a.txn_date
    db = b.settlement_date or b.txn_date
    if not da or not db:
        return True
    return abs((da - db).days) <= sla_days + 1


def exact_match(
    txns: list[NormalizedTxn],
    sla_days: int = 2,
) -> tuple[list[MatchGroup], list[NormalizedTxn]]:
    """Return (auto-matched groups, leftover unmatched txns)."""

    by_source: dict[Source, list[NormalizedTxn]] = defaultdict(list)
    for t in txns:
        by_source[t.source].append(t)

    consumed: set[int] = set()
    groups: list[MatchGroup] = []

    # Index pg and bank by UTR.
    pg_by_utr: dict[str, list[int]] = defaultdict(list)
    bank_by_utr: dict[str, list[int]] = defaultdict(list)
    for idx, t in enumerate(txns):
        k = _key_utr(t)
        if not k:
            continue
        if t.source is Source.PG:
            pg_by_utr[k].append(idx)
        elif t.source is Source.BANK:
            bank_by_utr[k].append(idx)

    for idx, led in enumerate(txns):
        if led.source is not Source.LEDGER or idx in consumed:
            continue
        k = _key_utr(led)
        if not k or k not in pg_by_utr:
            continue

        pg_idx = next((p for p in pg_by_utr[k] if p not in consumed), None)
        if pg_idx is None:
            continue
        pg = txns[pg_idx]

        bank_idx = next(
            (
                b
                for b in bank_by_utr.get(k, [])
                if b not in consumed
                and abs(txns[b].amount_net - pg.amount_net) <= AMOUNT_TOLERANCE_INR
                and _within_window(pg, txns[b], sla_days)
            ),
            None,
        )

        # ledger <-> pg gross must agree within tolerance
        if abs(led.amount_gross - pg.amount_gross) > AMOUNT_TOLERANCE_INR:
            continue

        if bank_idx is None:
            continue  # leave for candidate generation (likely TIMING_GAP / MISSING_PAYOUT)

        consumed.update({idx, pg_idx, bank_idx})
        groups.append(
            MatchGroup(
                batch_id=led.batch_id,
                status="auto_matched",
                method=MatchMethod.EXACT,
                ledger_txn_id=led.raw_record_id,
                pg_txn_id=pg.raw_record_id,
                bank_txn_id=txns[bank_idx].raw_record_id,
                note=f"exact:utr={k}",
            )
        )

    leftovers = [t for i, t in enumerate(txns) if i not in consumed]
    return groups, leftovers

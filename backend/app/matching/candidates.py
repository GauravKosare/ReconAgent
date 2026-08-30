"""Stage 2 — for every leftover row, propose a small set of candidate matches.

Combines three cheap signals (all deterministic):
  * amount proximity
  * date proximity
  * fuzzy string similarity on narration / ids (RapidFuzz)

Optionally a semantic similarity score is added by the caller using embeddings
+ Atlas Vector Search. The output feeds the agent, which makes the final call.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from ..models import NormalizedTxn, Source

MAX_CANDIDATES = 3


@dataclass
class Candidate:
    txn: NormalizedTxn
    score: float
    signals: dict[str, float] = field(default_factory=dict)


@dataclass
class Cluster:
    """One unresolved row plus its best candidate counterparts from other sources."""

    cluster_id: str
    anchor: NormalizedTxn
    candidates: list[Candidate]


def _amount_signal(a: float, b: float) -> float:
    if max(abs(a), abs(b)) == 0:
        return 1.0
    return max(0.0, 1.0 - abs(a - b) / max(abs(a), abs(b)))


def _date_signal(a: NormalizedTxn, b: NormalizedTxn, sla_days: int) -> float:
    da = a.settlement_date or a.txn_date
    db = b.settlement_date or b.txn_date
    if not da or not db:
        return 0.5
    gap = abs((da - db).days)
    return max(0.0, 1.0 - gap / (sla_days + 5))


def _text_signal(a: NormalizedTxn, b: NormalizedTxn) -> float:
    parts = []
    if a.narration and b.narration:
        parts.append(fuzz.token_set_ratio(a.narration, b.narration) / 100.0)
    if a.utr and b.utr:
        parts.append(fuzz.ratio(a.utr, b.utr) / 100.0)
    if a.external_id and b.external_id:
        parts.append(fuzz.partial_ratio(a.external_id, b.external_id) / 100.0)
    return sum(parts) / len(parts) if parts else 0.0


def generate_candidates(
    leftovers: list[NormalizedTxn],
    sla_days: int = 2,
    weights: tuple[float, float, float] = (0.45, 0.2, 0.35),
) -> list[Cluster]:
    w_amt, w_date, w_text = weights
    by_source: dict[Source, list[NormalizedTxn]] = {s: [] for s in Source}
    for t in leftovers:
        by_source[t.source].append(t)

    clusters: list[Cluster] = []
    # Anchor on ledger rows first, then PG rows with no ledger partner.
    anchors = by_source[Source.LEDGER] + by_source[Source.PG]

    for n, anchor in enumerate(anchors):
        pool = [t for s in Source if s is not anchor.source for t in by_source[s]]
        scored: list[Candidate] = []
        for cand in pool:
            s_amt = _amount_signal(anchor.amount_net or anchor.amount_gross,
                                   cand.amount_net or cand.amount_gross)
            s_date = _date_signal(anchor, cand, sla_days)
            s_text = _text_signal(anchor, cand)
            total = w_amt * s_amt + w_date * s_date + w_text * s_text
            scored.append(
                Candidate(txn=cand, score=round(total, 4),
                          signals={"amount": round(s_amt, 3),
                                   "date": round(s_date, 3),
                                   "text": round(s_text, 3)})
            )
        scored.sort(key=lambda c: c.score, reverse=True)
        clusters.append(
            Cluster(
                cluster_id=f"{anchor.batch_id}:c{n}",
                anchor=anchor,
                candidates=scored[:MAX_CANDIDATES],
            )
        )
    return clusters

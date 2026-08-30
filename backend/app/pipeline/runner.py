"""End-to-end batch orchestration. Deterministic core first, agent only for the
unresolved remainder, then routing, persistence and metrics.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from ..agent.adjudicator import adjudicate_cluster
from ..agent.model_client import ModelClient, ModelUnavailable
from ..audit.log import audit
from ..ingest import normalize_file
from ..matching import exact_match
from ..matching.candidates import generate_candidates
from ..models import ExceptionRecord, RouteTarget, Source, VerdictType
from .routing import route_verdict


def run_batch(
    pg_path: str,
    bank_path: str,
    ledger_path: str,
    *,
    persist: bool = True,
    sla_days: int = 2,
) -> dict[str, Any]:
    batch_id = f"batch_{uuid.uuid4().hex[:10]}"
    started = datetime.utcnow()

    txns = (
        normalize_file(ledger_path, Source.LEDGER, batch_id)
        + normalize_file(pg_path, Source.PG, batch_id)
        + normalize_file(bank_path, Source.BANK, batch_id)
    )
    audit(batch_id, "system", "ingest", "batch", batch_id, after={"txn_count": len(txns)})

    matched, leftovers = exact_match(txns, sla_days=sla_days)
    clusters = generate_candidates(leftovers, sla_days=sla_days)

    client = ModelClient()
    same_source_index: dict[Source, list] = {s: [t for t in txns if t.source is s] for s in Source}

    exceptions: list[ExceptionRecord] = []
    agent_runs: list[dict] = []
    routed_counts = {RouteTarget.AUTO_RESOLVED: 0, RouteTarget.PENDING_APPROVAL: 0}
    llm_used = False

    for cluster in clusters:
        try:
            verdict, meta = adjudicate_cluster(
                cluster, same_source_index[cluster.anchor.source], client=client
            )
            llm_used = True
            agent_runs.append(meta)
        except ModelUnavailable as exc:
            # No brain available -> everything unresolved goes to a human.
            audit(batch_id, "system", "llm_unavailable", "cluster", cluster.cluster_id,
                  after={"reason": str(exc)})
            exceptions.append(
                ExceptionRecord(
                    batch_id=batch_id, cluster_id=cluster.cluster_id,
                    code="UNEXPLAINED", amount_impact=0.0, direction="neutral",
                    confidence=0.0, rationale="No LLM configured; manual review required.",
                    routed_to=RouteTarget.PENDING_APPROVAL,
                )
            )
            routed_counts[RouteTarget.PENDING_APPROVAL] += 1
            continue

        target, reason = route_verdict(verdict)
        routed_counts[target] += 1

        if verdict.verdict is not VerdictType.MATCHED:
            exceptions.append(
                ExceptionRecord(
                    batch_id=batch_id,
                    cluster_id=cluster.cluster_id,
                    code=verdict.exception_code or "UNEXPLAINED",
                    amount_impact=verdict.amount_impact,
                    direction=verdict.direction,
                    confidence=verdict.confidence,
                    rationale=verdict.rationale,
                    evidence=verdict.evidence,
                    recommended_action=verdict.recommended_action,
                    routed_to=target,
                )
            )
        audit(batch_id, "agent", "adjudicate", "cluster", cluster.cluster_id,
              after={"verdict": verdict.model_dump(mode="json"), "route": target.value, "reason": reason})

    total = max(len(txns) // 3, 1)  # rough denominator: transactions, not rows
    summary = {
        "batch_id": batch_id,
        "started_at": started.isoformat(),
        "finished_at": datetime.utcnow().isoformat(),
        "runtime_seconds": round((datetime.utcnow() - started).total_seconds(), 1),
        "rows_ingested": len(txns),
        "auto_matched_groups": len(matched),
        "auto_match_rate": round(len(matched) / total, 3),
        "clusters_adjudicated": len(clusters),
        "exceptions": len(exceptions),
        "exceptions_by_code": _count_by_code(exceptions),
        "auto_resolved": routed_counts[RouteTarget.AUTO_RESOLVED],
        "pending_approval": routed_counts[RouteTarget.PENDING_APPROVAL],
        "flagged_amount_inr": round(sum(abs(e.amount_impact) for e in exceptions), 2),
        "llm_used": llm_used,
        "llm_available": client.available,
    }

    if persist:
        _persist(batch_id, txns, matched, exceptions, agent_runs, summary)

    return {"summary": summary, "exceptions": [e.model_dump(mode="json") for e in exceptions]}


def _count_by_code(exceptions: list[ExceptionRecord]) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in exceptions:
        key = e.code if isinstance(e.code, str) else e.code.value
        out[key] = out.get(key, 0) + 1
    return out


def _persist(batch_id, txns, matched, exceptions, agent_runs, summary) -> None:
    from ..db import ensure_indexes, get_db

    db = get_db()
    ensure_indexes()
    db.batches.insert_one({"_id": batch_id, **summary})
    if txns:
        db.normalized_txns.insert_many([t.model_dump(mode="json") for t in txns])
    if matched:
        db.match_groups.insert_many([m.model_dump(mode="json") for m in matched])
    if exceptions:
        db.exceptions.insert_many([e.model_dump(mode="json") for e in exceptions])
    if agent_runs:
        db.agent_runs.insert_many(agent_runs)

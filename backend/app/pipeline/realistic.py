"""Reconciliation for real, multi-format statements with AGGREGATED bank payouts.

Flow:
  0. detect_and_parse each file  -> NormalizedTxn
  1. reconcile_settlements       -> auto-matched lines + batch outcomes + per-line issues
  2. batch outcomes that did not reconcile  -> MISSING_PAYOUT / TIMING_GAP /
     SPLIT_PAYOUT / SHORT_SETTLEMENT (deterministic: expected vs actual payout)
  3. per-line issues  -> FEE_MISMATCH / MISSING_IN_LEDGER / SHORT_SETTLEMENT /
     DUPLICATE (deterministic: line vs contract, line vs ledger)
  4. an LLM (if configured) writes the human rationale + recommended action for
     each exception and can flag a disagreement — it never changes the code or ₹.
  5. routing + scorecard shape identical to run_batch.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from ..agent.model_client import ModelClient, ModelUnavailable
from ..config import get_settings
from ..ingest.formats import detect_and_parse
from ..matching.settlement import BatchOutcome, LineIssue, reconcile_settlements
from ..models import ExceptionRecord, RouteTarget, Source

_ALWAYS_HUMAN = {"MISSING_PAYOUT", "SHORT_SETTLEMENT", "MISSING_IN_LEDGER", "SPLIT_PAYOUT", "CHARGEBACK", "UNEXPLAINED"}
_AUTO_MAX_INR = None  # set from config at call time

_ACTION = {
    "FEE_MISMATCH": "Raise a fee-dispute ticket with the PG",
    "SHORT_SETTLEMENT": "Query the PG for the unexplained deduction",
    "MISSING_PAYOUT": "Escalate to PG settlements — payout past SLA",
    "TIMING_GAP": "No action; recheck after the next bank sync",
    "MISSING_IN_LEDGER": "Ask ops to record the missing sale in the ledger",
    "DUPLICATE": "Void the duplicate entry after confirmation",
    "SPLIT_PAYOUT": "Chase the missing Route split leg",
}

_SYS = (
    "You are ReconAgent. You are given a reconciliation exception already classified "
    "and sized by deterministic rules. Return JSON {\"confidence\": 0..1, \"rationale\": "
    "\"<=40 words, specific, with numbers\", \"recommended_action\": \"...\", \"agree\": true|false}. "
    "Confirm unless a number looks wrong; never restate the code."
)


def _route(code: str, impact: float, confidence: float) -> RouteTarget:
    s = get_settings()
    if code in _ALWAYS_HUMAN:
        return RouteTarget.PENDING_APPROVAL
    if confidence >= s.auto_resolve_min_confidence and abs(impact) <= s.auto_resolve_max_impact_inr:
        return RouteTarget.AUTO_RESOLVED
    return RouteTarget.PENDING_APPROVAL


def _batch_records(batch_id: str, outcomes: list[BatchOutcome]) -> list[ExceptionRecord]:
    out: list[ExceptionRecord] = []
    for b in outcomes:
        if b.reconciled:
            continue
        payments = [p for p in b.pg_lines if p.kind != "refund"]
        shortfall = round(b.expected_payout - b.actual_payout, 2)
        if not b.bank_rows:
            code, impact, direction = "MISSING_PAYOUT", b.expected_payout, "merchant_owed"
        elif b.reason == "payout late":
            code, impact, direction = "TIMING_GAP", 0.0, "neutral"
        elif len(b.bank_rows) >= 2 and shortfall > 1:
            code, impact, direction = "SPLIT_PAYOUT", shortfall, "merchant_owed"
        else:
            code, impact, direction = "SHORT_SETTLEMENT", abs(shortfall), "merchant_owed"

        base_rationale = (
            f"Settlement {b.settlement_id}: {len(payments)} payments, expected payout "
            f"₹{b.expected_payout:.2f}, bank shows ₹{b.actual_payout:.2f} "
            f"across {len(b.bank_rows)} credit(s)."
        )
        for j, p in enumerate(payments):
            out.append(
                ExceptionRecord(
                    batch_id=batch_id,
                    cluster_id=f"setl:{b.settlement_id}" + ("" if j == 0 else f":{p.raw_record_id}"),
                    anchor_source="pg", anchor_external_id=p.external_id, anchor_utr=b.settlement_utr,
                    code=code,
                    amount_impact=round(p.amount_net if code in ("MISSING_PAYOUT",) else
                                        (impact if j == 0 else 0.0) if code == "SPLIT_PAYOUT" else
                                        (0.0 if code == "TIMING_GAP" else round(shortfall / max(len(payments), 1), 2)), 2),
                    direction=direction, confidence=0.9, rationale=base_rationale,
                    evidence=[f"expected={b.expected_payout}", f"actual={b.actual_payout}",
                              f"bank_rows={len(b.bank_rows)}"],
                    recommended_action=_ACTION.get(code, "Send to reviewer"),
                    routed_to=RouteTarget.PENDING_APPROVAL,
                )
            )
    return out


def _line_records(batch_id: str, issues: list[LineIssue]) -> list[ExceptionRecord]:
    out: list[ExceptionRecord] = []
    for it in issues:
        conf = 0.75
        out.append(
            ExceptionRecord(
                batch_id=batch_id, cluster_id=f"line:{it.pg.raw_record_id}",
                anchor_source=it.pg.source.value,
                anchor_external_id=it.pg.external_id, anchor_utr=it.pg.utr,
                code=it.code, amount_impact=round(abs(it.impact), 2),
                direction="merchant_owed" if it.code in ("FEE_MISMATCH", "SHORT_SETTLEMENT", "MISSING_IN_LEDGER") else "neutral",
                confidence=conf, rationale=f"[deterministic] {it.detail}",
                evidence=[f"pg={it.pg.raw_record_id}", f"ledger={it.ledger.raw_record_id if it.ledger else None}"],
                recommended_action=_ACTION.get(it.code, "Send to reviewer"),
                routed_to=RouteTarget.PENDING_APPROVAL,
            )
        )
    return out


def _enrich(records: list[ExceptionRecord], client: ModelClient) -> bool:
    if not client.available or not records:
        return False
    import json

    def one(rec: ExceptionRecord):
        try:
            r = client.complete(_SYS, json.dumps({
                "code": rec.code, "amount_impact": rec.amount_impact,
                "rationale": rec.rationale, "evidence": rec.evidence,
            }), max_tokens=400)
            d = r.json()
            if d.get("rationale"):
                rec.rationale = str(d["rationale"])[:400]
            if d.get("recommended_action"):
                rec.recommended_action = str(d["recommended_action"])[:200]
            rec.confidence = float(d.get("confidence") or rec.confidence)
            if d.get("agree") is False:
                rec.confidence = min(rec.confidence, 0.5)
                rec.evidence.append("agent flagged for review")
        except (ModelUnavailable, ValueError, TypeError):
            pass

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(one, records))
    return True


def run_realistic_batch(
    pg_path: str, bank_path: str, ledger_path: str, *, persist: bool = False,
    tds_percent: float | None = None, reserve_percent: float | None = None,
) -> dict[str, Any]:
    s = get_settings()
    batch_id = f"rbatch_{uuid.uuid4().hex[:10]}"
    started = datetime.now(UTC).replace(tzinfo=None)

    txns, formats = [], {}
    for path in (ledger_path, pg_path, bank_path):
        src, fmt, parsed = detect_and_parse(path, batch_id)
        formats[src.value] = fmt
        txns.extend(parsed)

    recon = reconcile_settlements(
        txns, sla_days=s.settlement_sla_days,
        mdr_percent=s.default_mdr_percent, gst_percent=s.default_gst_percent,
        tds_percent=s.default_tds_percent if tds_percent is None else tds_percent,
        reserve_percent=s.default_reserve_percent if reserve_percent is None else reserve_percent,
    )

    exceptions = _batch_records(batch_id, recon.batches) + _line_records(batch_id, recon.line_issues)

    client = ModelClient()
    llm_used = _enrich(exceptions, client)

    for e in exceptions:
        e.routed_to = _route(
            e.code if isinstance(e.code, str) else e.code.value, e.amount_impact, e.confidence
        )

    txn_count = len([t for t in txns if t.source is Source.PG and t.kind != "refund"])
    pending = sum(1 for e in exceptions if e.routed_to == RouteTarget.PENDING_APPROVAL)
    auto = sum(1 for e in exceptions if e.routed_to == RouteTarget.AUTO_RESOLVED)
    summary = {
        "batch_id": batch_id,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "runtime_seconds": round((datetime.now(UTC).replace(tzinfo=None) - started).total_seconds(), 1),
        "rows_ingested": len(txns),
        "formats": formats,
        "settlement_batches": len(recon.batches),
        "batches_reconciled": recon.batch_report["reconciled"],
        "auto_matched_groups": len(recon.groups),
        "auto_match_rate": round(len(recon.groups) / max(txn_count, 1), 3),
        "clusters_adjudicated": len(exceptions),
        "exceptions": len(exceptions),
        "exceptions_by_code": _count(exceptions),
        "auto_resolved": auto,
        "pending_approval": pending,
        "flagged_amount_inr": round(sum(abs(e.amount_impact) for e in exceptions), 2),
        "llm_used": llm_used,
        "llm_available": client.available,
    }
    return {"summary": summary, "exceptions": [e.model_dump(mode="json") for e in exceptions]}


def _count(rows: list[ExceptionRecord]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = r.code if isinstance(r.code, str) else r.code.value
        out[k] = out.get(k, 0) + 1
    return out

"""Stage 3 — agent adjudication of one unresolved cluster.

Design:
  * Python first computes a deterministic assessment (`matching.compute_signals`)
    with a `suggested_code`. This is what actually drives accuracy.
  * The LLM ADJUDICATES that suggestion in one stateless call: confirm it, or
    override it and name the signal that is wrong. It also writes the
    human-readable rationale + recommended action.
  * Money is owned by Python: `amount_impact` always comes from the signals,
    never from the model.
  * No LLM available / unparseable output -> `deterministic_verdict` is used.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from ..config import get_settings
from ..matching.candidates import Cluster
from ..matching.signals import Signals, compute_signals
from ..models import ExceptionCode, Verdict, VerdictType
from .model_client import ModelClient
from .taxonomy import TAXONOMY

SYSTEM_PROMPT = """You are ReconAgent, a finance-operations reconciliation analyst.

You are given ONE transaction cluster (an anchor row + candidate counterpart rows
from the other sources) and, most importantly, a `signals` object: a
DETERMINISTIC assessment already computed in Python, including `suggested_verdict`,
`suggested_code`, `suggested_amount_impact` and the `reason` the rule fired.

Your job is to ADJUDICATE that suggestion. Python owns the final label; you
either agree or you flag a disagreement for a human — you never change the
number.
- If the signals support the suggestion, return the SAME verdict and code with
  confidence >= 0.9.
- If a specific signal looks wrong or misleading, return YOUR best verdict/code
  and name the exact signal field in the rationale (this routes to a human).
- Always write a concise `rationale` (<= 40 words, specific, with numbers) and a
  `recommended_action`.

Do not do arithmetic. Do not invent rows.

Taxonomy (for reference):
{taxonomy}

Return ONLY a JSON object:
  verdict ("matched"|"exception"|"unexplained"),
  exception_code (one taxonomy code or null),
  confidence (number 0..1),
  rationale (string),
  recommended_action (string)
"""


def _ref_date(cluster: Cluster, same_source_rows: list) -> datetime | None:
    """'As of' date for SLA checks: the latest date anywhere in the batch plus a
    few days (a reconciliation report is pulled after the period closes)."""
    dates = [
        d
        for row in [*same_source_rows, *(c.txn for c in cluster.candidates), cluster.anchor]
        for d in (row.txn_date, row.settlement_date)
        if d
    ]
    return max(dates) + timedelta(days=3) if dates else None


def _row_view(t) -> dict:
    return {
        "id": t.raw_record_id,
        "source": t.source.value,
        "external_id": t.external_id,
        "utr": t.utr,
        "gross": t.amount_gross,
        "fee": t.fee,
        "tax": t.tax,
        "net": t.amount_net,
        "txn_date": t.txn_date.isoformat() if t.txn_date else None,
        "settlement_date": t.settlement_date.isoformat() if t.settlement_date else None,
        "narration": t.narration,
    }


def build_context(cluster: Cluster, same_source_rows: list) -> tuple[Signals, dict]:
    s = get_settings()
    signals = compute_signals(
        cluster,
        same_source_rows,
        mdr_percent=s.default_mdr_percent,
        gst_percent=s.default_gst_percent,
        sla_days=s.settlement_sla_days,
        ref_date=_ref_date(cluster, same_source_rows),
    )
    context = {
        "anchor": _row_view(cluster.anchor),
        "candidates": [
            {**_row_view(c.txn), "match_score": c.score} for c in cluster.candidates
        ],
        "signals": signals.as_dict(),
    }
    return signals, context


def deterministic_verdict(cluster: Cluster, signals: Signals) -> Verdict:
    """Verdict straight from the deterministic signals (no LLM)."""
    return Verdict(
        cluster_id=cluster.cluster_id,
        verdict=VerdictType(signals.suggested_verdict),
        match_group=[cluster.anchor.raw_record_id]
        + ([signals.best_candidate_id] if signals.best_candidate_id else []),
        exception_code=ExceptionCode(signals.suggested_code) if signals.suggested_code else None,
        amount_impact=signals.suggested_amount_impact,
        direction=signals.suggested_direction,
        confidence=0.75 if signals.suggested_verdict == "exception" else 0.6,
        rationale=f"[deterministic] {signals.reason}",
        evidence=[f"signals.reason={signals.reason}", f"sources={signals.sources_in_cluster}"],
        recommended_action=_action_for(signals.suggested_code, signals.suggested_amount_impact),
    )


def _action_for(code: str | None, impact: float) -> str:
    return {
        "FEE_MISMATCH": f"Raise a fee-dispute ticket for INR {impact:.2f}",
        "SHORT_SETTLEMENT": f"Query the PG for the unexplained INR {impact:.2f} deduction",
        "MISSING_PAYOUT": "Escalate to PG settlements — payout past SLA",
        "TIMING_GAP": "No action; recheck after the next bank sync",
        "MISSING_IN_LEDGER": "Ask ops to record the missing sale in the ledger",
        "DUPLICATE": "Void the duplicate entry after confirmation",
    }.get(code or "", "Send to reviewer")


def adjudicate_cluster(
    cluster: Cluster,
    same_source_rows: list,
    client: ModelClient | None = None,
) -> tuple[Verdict, dict]:
    """Return (verdict, agent_run_metadata). Raises ModelUnavailable upstream."""
    client = client or ModelClient()
    signals, context = build_context(cluster, same_source_rows)

    system = SYSTEM_PROMPT.format(
        taxonomy="\n".join(f"- {c.value}: {d}" for c, d in TAXONOMY.items())
    )
    result = client.complete(system, json.dumps(context, default=str, indent=2), max_tokens=900)

    try:
        data = result.json()
    except (ValueError, TypeError):
        data = {}

    llm_verdict = _safe_enum(VerdictType, data.get("verdict"), None)
    llm_code = _safe_enum(ExceptionCode, data.get("exception_code"), None)

    # The deterministic signals ARE the classification — the LLM never silently
    # changes a money decision. Its role is to (a) write the human-readable
    # rationale + recommended action, (b) give a confidence, and (c) FLAG
    # disagreement so a human looks at it (we lower confidence, routing does the
    # rest). This keeps classification accuracy == the accuracy of the rules.
    verdict = deterministic_verdict(cluster, signals)
    llm_confirms = (
        llm_verdict is verdict.verdict
        and (llm_code == verdict.exception_code or verdict.verdict is not VerdictType.EXCEPTION)
    )

    if data:
        if data.get("rationale"):
            verdict.rationale = str(data["rationale"])[:400]
        if data.get("recommended_action"):
            verdict.recommended_action = str(data["recommended_action"])[:200]
        if llm_confirms:
            verdict.confidence = max(
                verdict.confidence, float(data.get("confidence") or 0.9)
            )
        elif llm_verdict is not None:
            verdict.confidence = min(verdict.confidence, 0.55)
            verdict.evidence.append(
                f"agent disagrees: suggested {signals.suggested_code}, "
                f"agent said {llm_code or llm_verdict} -> human review"
            )
    else:
        # unparseable model output -> keep deterministic verdict, flag for review
        verdict.confidence = min(verdict.confidence, 0.6)
        verdict.evidence.append("agent output unparseable -> human review")

    # Money is always Python's.
    verdict.amount_impact = (
        0.0 if verdict.verdict is VerdictType.MATCHED else signals.suggested_amount_impact
    )

    meta = {
        "cluster_id": cluster.cluster_id,
        "model": result.model,
        "attempts": result.attempts,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "latency_ms": result.latency_ms,
        "signals": signals.as_dict(),
        "raw_response": result.content,
        "created_at": datetime.now(UTC).replace(tzinfo=None),
    }
    return verdict, meta


def _safe_enum(enum_cls, value, default):
    if value in (None, ""):
        return default
    try:
        return enum_cls(value)
    except ValueError:
        return default

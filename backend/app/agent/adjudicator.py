"""Stage 3 — agent adjudication of one unresolved cluster.

Design choices:
  * One LLM call per cluster (stateless) — bounded cost, easy to audit.
  * The model receives a pre-computed tool report so a single round-trip is
    usually enough; a follow-up round is allowed for `UNEXPLAINED` doubt.
  * Output is validated against the `Verdict` schema. `amount_impact` is
    re-derived in Python; a mismatch forces the cluster to a human.
"""

from __future__ import annotations

import json
from datetime import datetime

from ..config import get_settings
from ..matching.candidates import Cluster
from ..models import ExceptionCode, Verdict, VerdictType
from .model_client import ModelClient
from .taxonomy import TAXONOMY
from .tools import (
    tool_check_duplicate,
    tool_date_delta,
    tool_recompute_expected_fee,
    tool_within_settlement_sla,
)

SYSTEM_PROMPT = """You are ReconAgent, a finance-operations reconciliation analyst.
You are given ONE unresolved transaction cluster: an anchor row from one source
and up to three candidate counterpart rows from the other sources, plus a
deterministic TOOL REPORT computed for you.

Your job:
1. Decide whether the anchor actually matches one of the candidates.
2. If it matches but with a discrepancy, classify the discrepancy using EXACTLY
   one code from the taxonomy.
3. If nothing plausibly matches and no code fits, return "unexplained".

Rules:
- Do NOT do arithmetic yourself. Cite figures from the TOOL REPORT as evidence.
- confidence is your calibrated probability the verdict is correct (0..1).
- Never invent a bank credit or ledger row that is not in the data.
- Keep rationale under 60 words, plain English, specific with numbers.

Decide the code with THIS checklist, in order — use the FIRST that applies:
1. check_duplicate.is_duplicate == true                      -> DUPLICATE
2. anchor is `pg`/`bank` and no candidate has source `ledger` -> MISSING_IN_LEDGER
3. amounts of anchor and a candidate agree, but that candidate is a bank/
   settlement row whose date_delta_days is beyond the SLA        -> TIMING_GAP
4. no bank/settlement candidate exists at all AND
   within_settlement_sla.within_sla == false                     -> MISSING_PAYOUT
5. recompute_expected_fee.net_delta_short_paid is > 1 rupee      -> FEE_MISMATCH
   (if net_delta is ~0, the fee is CORRECT — do NOT pick FEE_MISMATCH)
6. net paid is materially below expected for another reason      -> SHORT_SETTLEMENT
7. amounts and dates all agree                                   -> verdict "matched"
8. none of the above                                             -> "unexplained"

amount_impact:
- FEE_MISMATCH / SHORT_SETTLEMENT: the rupee shortfall (net_delta).
- TIMING_GAP / MISSING_PAYOUT / MISSING_IN_LEDGER: the anchor's net amount.
- matched: 0.

Return ONLY a JSON object with keys:
  verdict ("matched"|"exception"|"unexplained"),
  match_group (list of row ids you believe belong together),
  exception_code (one taxonomy code or null),
  amount_impact (number, rupees, 0 if none),
  direction ("merchant_owed"|"merchant_owes"|"neutral"),
  confidence (number),
  rationale (string),
  evidence (list of strings),
  recommended_action (string).
"""


def _safe_enum(enum_cls, value, default):
    """Coerce a model-supplied string to an enum member, or fall back."""
    if value is None:
        return default
    try:
        return enum_cls(value)
    except ValueError:
        return default


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
        "status": t.status,
    }


def _tool_report(cluster: Cluster, same_source_rows: list) -> dict:
    s = get_settings()
    anchor = cluster.anchor
    fee = tool_recompute_expected_fee(anchor, s.default_mdr_percent, s.default_gst_percent)
    dates = [
        d
        for row in [*same_source_rows, *(c.txn for c in cluster.candidates), anchor]
        for d in (row.txn_date, row.settlement_date)
        if d
    ]
    ref_date = max(dates) if dates else None
    rep = {
        "recompute_expected_fee(anchor)": fee,
        "within_settlement_sla(anchor)": tool_within_settlement_sla(
            anchor, s.settlement_sla_days, ref_date
        ),
        "check_duplicate(anchor)": tool_check_duplicate(anchor, same_source_rows),
        "candidates": [],
    }
    for c in cluster.candidates:
        rep["candidates"].append(
            {
                "id": c.txn.raw_record_id,
                "match_score": c.score,
                "signals": c.signals,
                "date_delta_days": tool_date_delta(anchor.txn_date, c.txn.txn_date),
            }
        )
    return rep


def adjudicate_cluster(
    cluster: Cluster,
    same_source_rows: list,
    client: ModelClient | None = None,
) -> tuple[Verdict, dict]:
    """Return (verdict, agent_run_metadata).

    Raises ModelUnavailable if no LLM can answer — caller routes to human.
    """

    client = client or ModelClient()
    tool_report = _tool_report(cluster, same_source_rows)

    user = json.dumps(
        {
            "taxonomy": {c.value: d for c, d in TAXONOMY.items()},
            "anchor": _row_view(cluster.anchor),
            "candidates": [_row_view(c.txn) for c in cluster.candidates],
            "tool_report": tool_report,
        },
        default=str,
        indent=2,
    )

    result = client.complete(SYSTEM_PROMPT, user, max_tokens=1500)
    try:
        data = result.json()
    except (ValueError, TypeError) as exc:
        # Unparseable model output -> treat as unexplained, send to a human.
        data = {
            "verdict": "unexplained",
            "confidence": 0.0,
            "rationale": f"model output could not be parsed ({exc.__class__.__name__})",
            "evidence": [f"raw: {result.content[:200]}"],
        }

    verdict = Verdict(
        cluster_id=cluster.cluster_id,
        verdict=_safe_enum(VerdictType, data.get("verdict"), VerdictType.UNEXPLAINED),
        match_group=data.get("match_group", []),
        exception_code=_safe_enum(ExceptionCode, data.get("exception_code"), None),
        amount_impact=float(data.get("amount_impact", 0) or 0),
        direction=data.get("direction", "neutral"),
        confidence=float(data.get("confidence", 0) or 0),
        rationale=data.get("rationale", ""),
        evidence=data.get("evidence", []),
        recommended_action=data.get("recommended_action", ""),
    )

    # Guardrail: the money figure is OWNED BY CODE, not the model. For the
    # deduction-type codes we overwrite amount_impact with the Python-computed
    # net delta from the tool report; the model only decides the code.
    fee = tool_report["recompute_expected_fee(anchor)"]
    net_delta = round(abs(fee["net_delta_short_paid"]), 2)
    if verdict.exception_code in (ExceptionCode.FEE_MISMATCH, ExceptionCode.SHORT_SETTLEMENT):
        if abs(verdict.amount_impact - net_delta) > 1.0:
            verdict.evidence.append(
                f"guardrail: replaced agent impact {verdict.amount_impact} with tool net_delta {net_delta}"
            )
        verdict.amount_impact = net_delta
        verdict.direction = "merchant_owed"

    meta = {
        "cluster_id": cluster.cluster_id,
        "model": result.model,
        "attempts": result.attempts,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "latency_ms": result.latency_ms,
        "tool_calls": tool_report,
        "raw_response": result.content,
        "created_at": datetime.utcnow(),
    }
    return verdict, meta

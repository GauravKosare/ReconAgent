"""Deterministic tools the agent may call. Every tool is a pure function, returns
JSON-serialisable data, and is logged into `agent_runs.tool_calls`.

The agent never does arithmetic itself — it asks these tools and cites the
result as evidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..matching.fees import recompute_expected_fee
from ..models import NormalizedTxn


def tool_recompute_expected_fee(txn: NormalizedTxn, mdr: float, gst: float) -> dict[str, Any]:
    fe = recompute_expected_fee(txn, mdr_percent=mdr, gst_percent=gst)
    return {
        "expected_fee": fe.expected_fee,
        "expected_tax": fe.expected_tax,
        "expected_net": fe.expected_net,
        "actual_fee": fe.actual_fee,
        "actual_net": fe.actual_net,
        "fee_delta_overcharge": fe.fee_delta,
        "net_delta_short_paid": fe.net_delta,
        "within_tolerance": fe.within_tolerance,
    }


def tool_date_delta(d1: datetime | None, d2: datetime | None) -> dict[str, Any]:
    if not d1 or not d2:
        return {"days": None, "note": "missing date on one side"}
    return {"days": (d2 - d1).days}


def tool_within_settlement_sla(
    txn: NormalizedTxn, sla_days: int, ref_date: datetime | None = None
) -> dict[str, Any]:
    base = txn.settlement_date or txn.txn_date
    if not base:
        return {"within_sla": None}
    # "now" is the most recent date seen in the batch, not wall-clock — the data
    # is a historical export.
    now = ref_date or datetime.utcnow()
    age = (now - base).days
    return {"age_days": age, "sla_days": sla_days, "within_sla": age <= sla_days}


def tool_check_duplicate(txn: NormalizedTxn, same_source_rows: list[NormalizedTxn]) -> dict[str, Any]:
    hits = [
        r.raw_record_id
        for r in same_source_rows
        if r.raw_record_id != txn.raw_record_id
        and r.utr and txn.utr and r.utr == txn.utr
        and abs(r.amount_gross - txn.amount_gross) < 0.01
    ]
    return {"duplicate_of": hits, "is_duplicate": bool(hits)}


TOOL_SPECS = [
    {
        "name": "recompute_expected_fee",
        "description": "Recompute expected PG fee, tax and net for a transaction from the contracted MDR% and GST%.",
    },
    {"name": "date_delta", "description": "Days between two dates (d2 - d1)."},
    {"name": "within_settlement_sla", "description": "Whether a transaction is still inside its settlement SLA."},
    {"name": "check_duplicate", "description": "Whether a transaction is a duplicate of another row in the same source."},
]

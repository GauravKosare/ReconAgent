"""Pydantic schemas — the common transaction model and the agent contract."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Source(StrEnum):
    LEDGER = "ledger"
    PG = "pg"
    BANK = "bank"


class MatchMethod(StrEnum):
    EXACT = "exact"
    AGENT = "agent"
    MANUAL = "manual"


class ExceptionCode(StrEnum):
    FEE_MISMATCH = "FEE_MISMATCH"
    TIMING_GAP = "TIMING_GAP"
    MISSING_PAYOUT = "MISSING_PAYOUT"
    MISSING_IN_LEDGER = "MISSING_IN_LEDGER"
    SHORT_SETTLEMENT = "SHORT_SETTLEMENT"
    REFUND = "REFUND"
    CHARGEBACK = "CHARGEBACK"
    DUPLICATE = "DUPLICATE"
    FX_DIFF = "FX_DIFF"
    SPLIT_PAYOUT = "SPLIT_PAYOUT"
    UNEXPLAINED = "UNEXPLAINED"


class VerdictType(StrEnum):
    MATCHED = "matched"
    EXCEPTION = "exception"
    UNEXPLAINED = "unexplained"


class RouteTarget(StrEnum):
    AUTO_RESOLVED = "auto_resolved"
    PENDING_APPROVAL = "pending_approval"


class NormalizedTxn(BaseModel):
    """One row from any source, mapped to a common shape."""

    batch_id: str
    source: Source
    raw_record_id: str
    external_id: str | None = None          # payment_id / order_id / txn ref
    utr: str | None = None                   # UTR / RRN — the strongest cross-source key
    settlement_id: str | None = None         # PG settlement batch id (for aggregated payouts)
    method: str | None = None                # upi / card / netbanking / wallet
    kind: str = "payment"                    # payment | refund | adjustment
    amount_gross: float
    fee: float = 0.0
    tax: float = 0.0
    amount_net: float
    currency: str = "INR"
    txn_date: datetime | None = None
    settlement_date: datetime | None = None
    narration: str = ""
    status: str = ""
    narration_embedding: list[float] | None = None


class MatchGroup(BaseModel):
    batch_id: str
    status: str                              # auto_matched | agent_matched | unresolved
    method: MatchMethod
    ledger_txn_id: str | None = None
    pg_txn_id: str | None = None
    bank_txn_id: str | None = None
    note: str = ""


class Verdict(BaseModel):
    """The structured object the agent MUST return for each cluster.

    `amount_impact` is recomputed in Python from cited figures; if it disagrees
    with the agent's value the cluster is force-routed to a human.
    """

    cluster_id: str
    verdict: VerdictType
    match_group: list[str] = Field(default_factory=list)
    exception_code: ExceptionCode | None = None
    amount_impact: float = 0.0
    direction: str = "neutral"              # merchant_owed | merchant_owes | neutral
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    recommended_action: str = ""


class ExceptionRecord(BaseModel):
    batch_id: str
    match_group_id: str | None = None
    cluster_id: str
    anchor_source: str | None = None
    anchor_external_id: str | None = None
    anchor_utr: str | None = None
    code: ExceptionCode
    amount_impact: float
    direction: str
    confidence: float
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    routed_to: RouteTarget
    agent_run_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

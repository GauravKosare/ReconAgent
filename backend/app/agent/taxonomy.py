"""Exception taxonomy reference — shared by the agent prompt and the docs."""

from __future__ import annotations

from ..models import ExceptionCode

TAXONOMY: dict[ExceptionCode, str] = {
    ExceptionCode.FEE_MISMATCH: "PG fee/tax differs from the contracted MDR + GST rate.",
    ExceptionCode.TIMING_GAP: "Payment captured & settled by PG, bank credit not yet arrived but still within SLA.",
    ExceptionCode.MISSING_PAYOUT: "PG marked settled, no bank credit, SLA already breached.",
    ExceptionCode.MISSING_IN_LEDGER: "Money received (PG/bank) with no matching sale in the internal ledger.",
    ExceptionCode.SHORT_SETTLEMENT: "Net amount paid is less than expected net, with no fee/refund explanation.",
    ExceptionCode.REFUND: "Negative adjustment that matches a recorded refund.",
    ExceptionCode.CHARGEBACK: "Negative adjustment that matches a recorded dispute / chargeback.",
    ExceptionCode.DUPLICATE: "Same transaction recorded more than once within a single source.",
    ExceptionCode.FX_DIFF: "Multi-currency conversion / rounding delta.",
    ExceptionCode.SPLIT_PAYOUT: "One bank credit aggregates many PG settlement lines (Route / bulk payout).",
    ExceptionCode.UNEXPLAINED: "The agent cannot account for the difference — always sent to a human.",
}

# Codes whose money impact is inherently ambiguous / customer-facing and must
# never auto-resolve regardless of confidence.
ALWAYS_HUMAN = {
    ExceptionCode.MISSING_IN_LEDGER,
    ExceptionCode.SHORT_SETTLEMENT,
    ExceptionCode.CHARGEBACK,
    ExceptionCode.MISSING_PAYOUT,
    ExceptionCode.UNEXPLAINED,
}

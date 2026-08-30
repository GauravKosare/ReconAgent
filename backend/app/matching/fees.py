"""Deterministic fee / tax recomputation — used both as a matcher heuristic and
as a tool the agent can call to verify a FEE_MISMATCH."""

from __future__ import annotations

from dataclasses import dataclass

from ..models import NormalizedTxn


@dataclass
class FeeExpectation:
    expected_fee: float
    expected_tax: float
    expected_net: float
    actual_fee: float
    actual_net: float
    fee_delta: float          # actual - expected (positive => overcharged)
    net_delta: float          # expected - actual (positive => merchant short-paid)
    within_tolerance: bool


def recompute_expected_fee(
    txn: NormalizedTxn,
    mdr_percent: float = 2.0,
    gst_percent: float = 18.0,
    tolerance_inr: float = 0.5,
) -> FeeExpectation:
    expected_fee = round(txn.amount_gross * mdr_percent / 100.0, 2)
    expected_tax = round(expected_fee * gst_percent / 100.0, 2)
    expected_net = round(txn.amount_gross - expected_fee - expected_tax, 2)

    fee_delta = round(txn.fee - expected_fee, 2)
    net_delta = round(expected_net - txn.amount_net, 2)

    return FeeExpectation(
        expected_fee=expected_fee,
        expected_tax=expected_tax,
        expected_net=expected_net,
        actual_fee=txn.fee,
        actual_net=txn.amount_net,
        fee_delta=fee_delta,
        net_delta=net_delta,
        within_tolerance=abs(net_delta) <= tolerance_inr,
    )

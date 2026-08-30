from __future__ import annotations

from app.models import ExceptionCode, RouteTarget, Verdict, VerdictType
from app.pipeline.routing import route_verdict


def _v(**kw) -> Verdict:
    base = dict(
        cluster_id="c1",
        verdict=VerdictType.EXCEPTION,
        exception_code=ExceptionCode.FEE_MISMATCH,
        amount_impact=2.0,
        confidence=0.95,
        rationale="overcharged by 2",
    )
    base.update(kw)
    return Verdict(**base)


def test_small_high_confidence_fee_mismatch_auto_resolves():
    target, _ = route_verdict(_v())
    assert target is RouteTarget.AUTO_RESOLVED


def test_large_impact_forces_human():
    target, reason = route_verdict(_v(amount_impact=5000.0))
    assert target is RouteTarget.PENDING_APPROVAL
    assert "ceiling" in reason


def test_low_confidence_forces_human():
    target, _ = route_verdict(_v(confidence=0.6))
    assert target is RouteTarget.PENDING_APPROVAL


def test_missing_payout_always_human():
    target, _ = route_verdict(
        _v(exception_code=ExceptionCode.MISSING_PAYOUT, amount_impact=1.0, confidence=0.99)
    )
    assert target is RouteTarget.PENDING_APPROVAL


def test_unexplained_forces_human():
    target, _ = route_verdict(_v(verdict=VerdictType.UNEXPLAINED, exception_code=None))
    assert target is RouteTarget.PENDING_APPROVAL

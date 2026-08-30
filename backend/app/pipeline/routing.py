"""Stage 4 — bounded routing policy. This is CODE, not an LLM decision.

A verdict auto-resolves only when ALL hold:
  * verdict is an exception with a concrete code
  * code is in AUTO_RESOLVE_ALLOWED_CODES and not in ALWAYS_HUMAN
  * confidence >= AUTO_RESOLVE_MIN_CONFIDENCE
  * |amount_impact| <= AUTO_RESOLVE_MAX_IMPACT_INR
Everything else -> PENDING_APPROVAL.
"""

from __future__ import annotations

from ..agent.taxonomy import ALWAYS_HUMAN
from ..config import get_settings
from ..models import RouteTarget, Verdict, VerdictType


def route_verdict(verdict: Verdict) -> tuple[RouteTarget, str]:
    s = get_settings()

    if verdict.verdict is VerdictType.MATCHED:
        return RouteTarget.AUTO_RESOLVED, "clean match, no discrepancy"

    if verdict.verdict is VerdictType.UNEXPLAINED or verdict.exception_code is None:
        return RouteTarget.PENDING_APPROVAL, "unexplained / no code"

    if verdict.exception_code in ALWAYS_HUMAN:
        return RouteTarget.PENDING_APPROVAL, f"{verdict.exception_code.value} always needs a human"

    if verdict.exception_code.value not in s.allowed_auto_codes:
        return RouteTarget.PENDING_APPROVAL, "code not in auto-resolve allowlist"

    if verdict.confidence < s.auto_resolve_min_confidence:
        return RouteTarget.PENDING_APPROVAL, f"confidence {verdict.confidence:.2f} below floor"

    if abs(verdict.amount_impact) > s.auto_resolve_max_impact_inr:
        return RouteTarget.PENDING_APPROVAL, f"impact ₹{verdict.amount_impact:.2f} over ceiling"

    return RouteTarget.AUTO_RESOLVED, "within confidence + rupee bounds"

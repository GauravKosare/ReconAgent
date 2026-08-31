"""Foreign-exchange model for cross-border settlement.

A customer pays in a *presentment* currency; the gateway settles to the
merchant's account in the *settlement* currency, converting at the mid-market
rate minus a markup (spread). Reconciliation must verify that conversion.

Rates are static, plausible values for the 2026 window — not live. The point is
that the arithmetic (presentment -> mid rate -> spread -> settled) matches how
real gateways report FX.
"""

from __future__ import annotations

# Mid-market value of 1 unit of each currency in USD (approx, 2026).
_TO_USD: dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.09,
    "GBP": 1.27,
    "INR": 0.01198,   # ~83.5 INR / USD
    "AUD": 0.66,
    "SGD": 0.74,
    "CAD": 0.73,
    "JPY": 0.0067,
    "AED": 0.272,
    "CHF": 1.11,
    "SEK": 0.094,
}

# Gateway FX markup applied on top of the mid rate when converting.
DEFAULT_SPREAD = 0.02          # 2.0%
ZERO_DECIMAL = {"JPY"}         # currencies with no minor unit


def subunit_factor(currency: str) -> int:
    return 1 if currency in ZERO_DECIMAL else 100


def mid_rate(frm: str, to: str) -> float:
    """Units of `to` per 1 unit of `frm` at mid-market."""
    if frm == to:
        return 1.0
    return round(_TO_USD[frm] / _TO_USD[to], 6)


def convert(amount: float, frm: str, to: str, spread: float = DEFAULT_SPREAD) -> tuple[float, float]:
    """Return (settled_amount, effective_rate) for a presentment->settlement conversion.

    settled = amount * mid_rate * (1 - spread)   (merchant receives less)
    """
    if frm == to:
        return round(amount, 2), 1.0
    rate = mid_rate(frm, to)
    eff = round(rate * (1 - spread), 6)
    return round(amount * eff, 2), eff


def known_currencies() -> list[str]:
    return list(_TO_USD)

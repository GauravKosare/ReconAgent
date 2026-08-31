"""Money mechanics — now region-aware.

The merchant archetype (`Profile`) is geography-neutral: it says *what kind of
business* this is (order value in USD, refund/chargeback rates, marketplace vs
not). The `Region` (see regions.py) supplies the local facts — currency, tax
treatment, MDR bands, settlement cycle. `compute_fees` combines the two, and
handles the cross-border case where the customer pays in a foreign currency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .fx import DEFAULT_SPREAD, mid_rate
from .regions import Region

CARD_NETWORKS = ["Visa", "MasterCard", "American Express", "Discover"]
CARD_TYPES = ["credit", "debit"]
TDS_PCT = 0.01
ROLLING_RESERVE_PCT = 0.05
RESERVE_DAYS = 90

# a few plausible presentment currencies per settlement region for cross-border
FOREIGN_PRESENTMENT = {
    "INR": ["USD", "EUR", "GBP", "AED", "SGD"],
    "USD": ["EUR", "GBP", "CAD", "INR", "AUD"],
    "EUR": ["USD", "GBP", "INR", "CHF", "SEK"],
}


@dataclass(frozen=True)
class Profile:
    name: str
    aov_usd: float                # median order value in USD (lognormal)
    aov_sigma: float
    refund_rate: float
    chargeback_rate: float
    marketplace: bool = False
    rolling_reserve: bool = False
    method_bias: dict[str, float] | None = None  # nudges the region method mix


PROFILES: dict[str, Profile] = {
    "d2c-brand": Profile("d2c-brand", aov_usd=11.0, aov_sigma=0.6,
                         refund_rate=0.06, chargeback_rate=0.004),
    "saas": Profile("saas", aov_usd=30.0, aov_sigma=0.5,
                    refund_rate=0.03, chargeback_rate=0.006,
                    method_bias={"card": 1.6}),
    "marketplace": Profile("marketplace", aov_usd=8.0, aov_sigma=0.8,
                           refund_rate=0.09, chargeback_rate=0.005,
                           marketplace=True, rolling_reserve=True),
    "travel": Profile("travel", aov_usd=95.0, aov_sigma=0.7,
                      refund_rate=0.14, chargeback_rate=0.011,
                      rolling_reserve=True, method_bias={"card": 1.4}),
}


@dataclass
class Fees:
    mdr: float                    # processing fee in settlement currency
    tax: float                    # tax on the fee (0 unless region charges it)
    fx_markup: float              # gateway FX spread cost (cross-border only)
    currency: str

    @property
    def total(self) -> float:
        return round(self.mdr + self.tax + self.fx_markup, 2)


def _rate_to_usd(ccy: str) -> float:
    from .fx import _TO_USD
    return _TO_USD.get(ccy, 1.0)


def method_mix(region: Region, profile: Profile) -> dict[str, float]:
    mix = dict(region.method_mix)
    if profile.method_bias:
        for m, factor in profile.method_bias.items():
            if m in mix:
                mix[m] *= factor
    s = sum(mix.values())
    return {m: w / s for m, w in mix.items()}


def order_value(rng: random.Random, profile: Profile, region: Region) -> float:
    """Lognormal order value converted into the region's settlement currency."""
    import math
    usd = profile.aov_usd * math.exp(rng.gauss(0, profile.aov_sigma))
    usd = max(0.5, min(usd, profile.aov_usd * 25))
    local = usd / _rate_to_usd(region.currency)
    # round the way a real price would look
    return round(local, 0 if region.currency in ("INR", "JPY") else 2)


def expected_mdr(region: Region, method: str, gross: float) -> float:
    lo, hi, flat = region.mdr.get(method, (1.5, 2.5, 0.0))
    mid = (lo + hi) / 2 / 100.0
    return round(gross * mid + flat, 2)


def contracted_rates(rng: random.Random, region: Region) -> dict[str, tuple[float, float]]:
    """One fixed (pct, flat) per method for this merchant — a real contract has a
    rate, not a per-transaction band."""
    out: dict[str, tuple[float, float]] = {}
    for method, (lo, hi, flat) in region.mdr.items():
        out[method] = (round(rng.uniform(lo, hi) / 100.0, 5), flat)
    return out


def compute_fees(
    region: Region,
    method: str,
    gross_settlement: float,
    rates: dict[str, tuple[float, float]],
    *,
    cross_border: bool = False,
) -> Fees:
    pct, flat = rates.get(method, (0.02, 0.0))
    mdr = round(gross_settlement * pct + flat, 2)
    tax = region.taxed_fee(mdr)
    fx_markup = round(gross_settlement * DEFAULT_SPREAD, 2) if cross_border else 0.0
    return Fees(mdr=mdr, tax=tax, fx_markup=fx_markup, currency=region.currency)


def pick_presentment(rng: random.Random, region: Region, *, force: bool = False
                     ) -> tuple[str, float, float]:
    """Return (presentment_currency, mid_rate presentment->settlement, spread).

    Same currency => ('<settlement>', 1.0, 0.0). `force` guarantees cross-border.
    """
    if not force and rng.random() >= region.cross_border_share:
        return region.currency, 1.0, 0.0
    choices = FOREIGN_PRESENTMENT.get(region.currency, ["USD"])
    pres = rng.choice([c for c in choices if c != region.currency] or ["USD"])
    return pres, mid_rate(pres, region.currency), DEFAULT_SPREAD

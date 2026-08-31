"""Calibrated money mechanics for the realistic generator.

Numbers are order-of-magnitude realistic for Indian online payments (public
sources: NPCI UPI statistics, RBI payment-system data, published aggregator MDR
schedules). They are parameters, not claims of precision — the point is that the
*shape* of the data (method mix, fee structure, settlement timing) matches
reality so reconciliation logic is exercised the way it would be in production.
"""

from __future__ import annotations

from dataclasses import dataclass

GST_RATE = 0.18  # GST on the MDR fee


@dataclass(frozen=True)
class MethodEconomics:
    weight: float          # share of transaction count
    mdr_pct: float         # merchant discount rate on gross (0 for UPI P2M)
    flat_fee: float = 0.0  # flat per-txn fee in rupees (netbanking)
    intl_share: float = 0.0  # fraction of this method that is an international card


# Per payment method. Card MDR blends debit/credit/network.
METHODS: dict[str, MethodEconomics] = {
    "upi": MethodEconomics(weight=0.62, mdr_pct=0.0),
    "card": MethodEconomics(weight=0.24, mdr_pct=0.019, intl_share=0.06),
    "netbanking": MethodEconomics(weight=0.09, mdr_pct=0.0, flat_fee=12.0),
    "wallet": MethodEconomics(weight=0.05, mdr_pct=0.017),
}

CARD_NETWORKS = ["Visa", "MasterCard", "RuPay", "American Express"]
CARD_TYPES = ["credit", "debit"]

FOREX_MARKUP_PCT = 0.03        # markup on international card settlements
CROSS_BORDER_FEE_PCT = 0.005   # additional cross-border fee
TDS_PCT = 0.01                 # section 194-O, marketplace payouts only
ROLLING_RESERVE_PCT = 0.05     # held for reserve_days, released later
RESERVE_DAYS = 90


@dataclass(frozen=True)
class Profile:
    """A merchant archetype — drives volume mix, refunds, disputes, settlement."""

    name: str
    aov_median: float             # rupee median of a lognormal order value
    aov_sigma: float              # lognormal shape
    method_mix: dict[str, float]  # overrides METHODS weights
    refund_rate: float            # fraction of payments later refunded
    chargeback_rate: float        # fraction of payments disputed
    settlement_cycle_days: int    # T+N standard cycle
    instant_settlement_share: float
    marketplace: bool = False     # => TDS + split (Route) payouts
    rolling_reserve: bool = False
    intl_multiplier: float = 1.0  # scales each method's intl_share


PROFILES: dict[str, Profile] = {
    "d2c-brand": Profile(
        name="d2c-brand",
        aov_median=899, aov_sigma=0.6,
        method_mix={"upi": 0.66, "card": 0.22, "netbanking": 0.05, "wallet": 0.07},
        refund_rate=0.06, chargeback_rate=0.004,
        settlement_cycle_days=2, instant_settlement_share=0.10,
    ),
    "saas": Profile(
        name="saas",
        aov_median=2499, aov_sigma=0.5,
        method_mix={"upi": 0.34, "card": 0.55, "netbanking": 0.08, "wallet": 0.03},
        refund_rate=0.03, chargeback_rate=0.006,
        settlement_cycle_days=2, instant_settlement_share=0.05,
        intl_multiplier=3.0,
    ),
    "marketplace": Profile(
        name="marketplace",
        aov_median=649, aov_sigma=0.8,
        method_mix={"upi": 0.70, "card": 0.18, "netbanking": 0.06, "wallet": 0.06},
        refund_rate=0.09, chargeback_rate=0.005,
        settlement_cycle_days=1, instant_settlement_share=0.0,
        marketplace=True, rolling_reserve=True,
    ),
    "travel": Profile(
        name="travel",
        aov_median=7999, aov_sigma=0.7,
        method_mix={"upi": 0.28, "card": 0.60, "netbanking": 0.10, "wallet": 0.02},
        refund_rate=0.14, chargeback_rate=0.011,
        settlement_cycle_days=3, instant_settlement_share=0.0,
        rolling_reserve=True, intl_multiplier=2.0,
    ),
}


@dataclass
class Fees:
    mdr: float
    gst: float
    forex: float
    cross_border: float

    @property
    def total(self) -> float:
        return round(self.mdr + self.gst + self.forex + self.cross_border, 2)


def compute_fees(gross: float, method: str, is_intl: bool) -> Fees:
    m = METHODS[method]
    mdr = round(gross * m.mdr_pct + m.flat_fee, 2)
    gst = round(mdr * GST_RATE, 2)
    forex = round(gross * FOREX_MARKUP_PCT, 2) if is_intl else 0.0
    cb = round(gross * CROSS_BORDER_FEE_PCT, 2) if is_intl else 0.0
    return Fees(mdr=mdr, gst=gst, forex=forex, cross_border=cb)


def net_of(gross: float, fees: Fees) -> float:
    return round(gross - fees.total, 2)

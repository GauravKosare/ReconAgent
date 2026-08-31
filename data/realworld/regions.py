"""Jurisdiction models — IN, US, EU.

Each Region carries the facts the generator and the reconciler need to be
locally correct: currency, whether the processing fee is taxed, the regulated
MDR band per method, settlement rails + cycle, the payment-reference format,
number/date locale, banking holidays, and platform withholding.

Sources (public): RBI payment-system data & MDR caps (IN); EU Interchange Fee
Regulation 2015/751 caps of 0.2%% debit / 0.3%% credit and VAT Directive
2006/112/EC Art. 135(1)(d) exemption for payment services (EU); US card
network published rates + NACHA ACH conventions (US).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class TaxRule:
    name: str | None        # "GST" | "VAT" | None
    rate: float             # applied to the MDR fee
    treatment: str          # "charged" | "exempt" | "none"


@dataclass(frozen=True)
class Region:
    code: str               # ISO 3166-1 alpha-2
    name: str
    currency: str           # ISO 4217 settlement currency
    tax: TaxRule
    # expected MDR by method: (low_pct, high_pct, flat_fee_in_currency)
    mdr: dict[str, tuple[float, float, float]]
    method_mix: dict[str, float]
    rails: list[str]                 # settlement rails seen in bank narrations
    settlement_cycle_days: int
    instant_share: float
    id_label: str                   # "UTR" | "ACH trace" | "End-to-End ID"
    date_format: str                # strftime for statements
    decimal_sep: str                # "." or ","
    thousands_sep: str              # "," "." " " or ""
    grouping: str                   # "western" (1,234,567) | "indian" (12,34,567)
    default_bank_format: str        # emitter key: hdfc|icici|us_csv|camt|mt940
    default_pg_format: str          # "razorpay" (IN) | "stripe" (US/EU)
    withholding: tuple[str, float, str] | None  # (name, rate, applies_to)
    cross_border_share: float       # fraction of card payments in a foreign currency
    holidays: list[date] = field(default_factory=list)

    def taxed_fee(self, mdr_fee: float) -> float:
        return round(mdr_fee * self.tax.rate, 2) if self.tax.treatment == "charged" else 0.0


IN = Region(
    code="IN", name="India", currency="INR",
    tax=TaxRule("GST", 0.18, "charged"),
    mdr={
        "upi": (0.0, 0.0, 0.0),
        "card": (0.4, 2.0, 0.0),        # debit ~0.4-0.9, credit ~1.8-2.0
        "netbanking": (0.0, 0.0, 12.0),
        "wallet": (1.5, 2.0, 0.0),
    },
    method_mix={"upi": 0.62, "card": 0.24, "netbanking": 0.09, "wallet": 0.05},
    rails=["UPI", "NEFT", "IMPS", "RTGS"],
    settlement_cycle_days=2, instant_share=0.10,
    id_label="UTR", date_format="%d/%m/%y", decimal_sep=".", thousands_sep=",",
    grouping="indian", default_bank_format="hdfc", default_pg_format="razorpay",
    withholding=("TDS", 0.01, "marketplace"),
    cross_border_share=0.05,
    holidays=[date(2026, 8, 15)],  # Independence Day
)

US = Region(
    code="US", name="United States", currency="USD",
    tax=TaxRule(None, 0.0, "none"),        # payment processing not sales-taxed
    mdr={
        "card": (1.8, 2.9, 0.30),          # + $0.30 fixed, no cap
        "ach": (0.5, 1.0, 0.0),            # often capped ~$5 (approximated)
        "wallet": (1.9, 2.9, 0.30),
    },
    method_mix={"card": 0.74, "ach": 0.14, "wallet": 0.12},
    rails=["ACH", "WIRE", "RTP"],
    settlement_cycle_days=2, instant_share=0.05,
    id_label="ACH trace", date_format="%m/%d/%Y", decimal_sep=".", thousands_sep=",",
    grouping="western", default_bank_format="us_csv", default_pg_format="stripe",
    withholding=("Backup withholding", 0.24, "no_tin"),  # rare; only if TIN missing
    cross_border_share=0.14,
    holidays=[],  # no US federal banking holiday in the August window
)

EU = Region(
    code="EU", name="Euro area (DE)", currency="EUR",
    tax=TaxRule("VAT", 0.0, "exempt"),    # payment services VAT-exempt (Art. 135)
    mdr={
        "card": (0.2, 1.2, 0.0),          # IFR-capped consumer cards; commercial higher
        "sepa": (0.1, 0.5, 0.35),
        "ideal": (0.0, 0.0, 0.29),        # flat-fee scheme
        "wallet": (0.8, 1.6, 0.0),
    },
    method_mix={"card": 0.55, "sepa": 0.22, "ideal": 0.13, "wallet": 0.10},
    rails=["SEPA", "SEPA_INSTANT", "TARGET2"],
    settlement_cycle_days=1, instant_share=0.20,
    id_label="End-to-End ID", date_format="%d.%m.%Y", decimal_sep=",", thousands_sep=".",
    grouping="western", default_bank_format="camt", default_pg_format="stripe",
    withholding=None,
    cross_border_share=0.18,
    holidays=[date(2026, 8, 15)],  # Assumption Day (regional in DE)
)

REGIONS: dict[str, Region] = {"IN": IN, "US": US, "EU": EU}

"""What the reconciler needs to be locally correct, per jurisdiction.

Kept separate from the dataset generator's `Region` (which lives under data/) so
the backend has no dependency on the generator. The two are conceptually the
same table; if you add a region, add it in both.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegionRules:
    code: str
    currency: str
    # expected MDR by method: (low_pct, high_pct, flat_fee_in_currency)
    mdr: dict[str, tuple[float, float, float]]
    fee_tax_rate: float          # e.g. 0.18 GST
    fee_tax_charged: bool        # True only where the region taxes the fee (IN)
    fx_contract_spread: float    # the FX markup the merchant's contract allows
    tds_percent: float           # marketplace withholding
    reserve_percent: float       # rolling reserve
    date_pref: str = "dmy"       # 'dmy' | 'mdy'


_IN = RegionRules(
    code="IN", currency="INR",
    mdr={"upi": (0.0, 0.0, 0.0), "card": (0.4, 2.0, 0.0),
         "netbanking": (0.0, 0.0, 12.0), "wallet": (1.5, 2.0, 0.0)},
    fee_tax_rate=0.18, fee_tax_charged=True,
    fx_contract_spread=0.02, tds_percent=0.0, reserve_percent=0.0,
)
_US = RegionRules(
    code="US", currency="USD",
    mdr={"card": (1.8, 2.9, 0.30), "ach": (0.5, 1.0, 0.0), "wallet": (1.9, 2.9, 0.30)},
    fee_tax_rate=0.0, fee_tax_charged=False,
    fx_contract_spread=0.02, tds_percent=0.0, reserve_percent=0.0,
    date_pref="mdy",
)
_EU = RegionRules(
    code="EU", currency="EUR",
    mdr={"card": (0.2, 1.2, 0.0), "sepa": (0.1, 0.5, 0.35),
         "ideal": (0.0, 0.0, 0.29), "wallet": (0.8, 1.6, 0.0)},
    fee_tax_rate=0.0, fee_tax_charged=False,   # payment services VAT-exempt
    fx_contract_spread=0.02, tds_percent=0.0, reserve_percent=0.0,
)

RULES: dict[str, RegionRules] = {"IN": _IN, "US": _US, "EU": _EU}


def region_rules(code: str, *, tds_percent: float | None = None,
                 reserve_percent: float | None = None) -> RegionRules:
    base = RULES.get((code or "IN").upper(), _IN)
    if tds_percent is None and reserve_percent is None:
        return base
    from dataclasses import replace
    return replace(
        base,
        tds_percent=base.tds_percent if tds_percent is None else tds_percent,
        reserve_percent=base.reserve_percent if reserve_percent is None else reserve_percent,
    )

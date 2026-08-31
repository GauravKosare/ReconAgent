"""Build a realistic, region-aware settlement scenario.

payments (possibly in a foreign currency) -> settlement batches ->
aggregated bank payouts (in the region's currency) -> ledger entries -> truth key.

Region supplies currency, tax treatment, MDR bands, rails, settlement cycle,
holidays, withholding. Cross-border payments are presented in a foreign currency
and converted at settlement (mid rate minus the gateway spread).

Injected defects: FEE_MISMATCH, SHORT_SETTLEMENT, MISSING_IN_LEDGER, DUPLICATE,
FX_DIFF (per line); MISSING_PAYOUT, TIMING_GAP, SPLIT_PAYOUT (per batch).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .economics import (
    CARD_NETWORKS,
    CARD_TYPES,
    PROFILES,
    ROLLING_RESERVE_PCT,
    TDS_PCT,
    Profile,
    compute_fees,
    contracted_rates,
    method_mix,
    order_value,
    pick_presentment,
)
from .entities import bank, brand, city, customer, payment_ref, window_holidays
from .fx import convert
from .regions import REGIONS, Region

WINDOW_START = datetime(2026, 8, 1, 6, 0)


@dataclass
class Payment:
    payment_id: str
    order_id: str
    order_receipt: str
    rrn: str
    settlement_ref: str            # batch key, region-formatted (UTR / ACH trace / E2E)
    settlement_id: str
    kind: str                      # payment | refund
    method: str
    card_network: str | None
    card_issuer: str | None
    card_type: str | None
    # currency
    presentment_currency: str
    presentment_amount: float      # what the customer paid, in their currency
    settlement_currency: str
    fx_rate: float                 # presentment -> settlement effective rate (1.0 domestic)
    cross_border: bool
    gross: float                   # gross in SETTLEMENT currency
    # fees (settlement currency)
    contract_fee: float
    contract_tax: float
    charged_fee: float
    charged_tax: float
    fx_markup: float
    net: float                     # gross - charged fees - short delta
    captured_at: datetime
    settled_at: datetime
    on_hold: bool
    instant: bool
    dispute_id: str | None
    customer_name: str
    city: str


@dataclass
class Settlement:
    settlement_id: str
    settlement_ref: str
    currency: str
    created_at: datetime
    settled_at: datetime
    payments: list[Payment]
    tds: float
    reserve_hold: float
    net_payout: float
    bank_emitted: bool
    bank_value_date: datetime
    bank_rail: str
    split_parts: list[float] = field(default_factory=list)


@dataclass
class LedgerEntry:
    invoice_no: str
    invoice_date: datetime
    order_id: str
    order_receipt: str
    customer_name: str
    city: str
    presentment_currency: str
    presentment_amount: float
    settlement_currency: str
    gross: float                   # in settlement currency (booked value)
    method: str
    status: str


@dataclass
class Scenario:
    profile: str
    region: str
    currency: str
    merchant: str
    payments: list[Payment]
    settlements: list[Settlement]
    ledger: list[LedgerEntry]
    truth: list[dict]
    stats: dict


def _next_business_day(d: datetime, cycle: int, holidays: list[datetime]) -> datetime:
    hol = {h.date() for h in holidays}
    out = d + timedelta(days=cycle)
    while out.weekday() >= 5 or out.date() in hol:
        out += timedelta(days=1)
    return out


def _pick_method(rng: random.Random, mix: dict[str, float]) -> str:
    r, acc = rng.random(), 0.0
    for m, w in mix.items():
        acc += w
        if r <= acc:
            return m
    return next(iter(mix))


def _rid(rng: random.Random, n: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(rng.choice(alphabet) for _ in range(n))


def build_scenario(
    profile_name: str = "d2c-brand",
    region_code: str = "IN",
    payments: int = 500,
    seed: int = 7,
    defect_rate: float = 0.12,
) -> Scenario:
    rng = random.Random(seed)
    region: Region = REGIONS[region_code]
    p: Profile = PROFILES[profile_name]
    merchant = brand(rng, region_code)
    holidays = window_holidays(region_code)
    mix = method_mix(region, p)
    rates = contracted_rates(rng, region)
    card_methods = {"card", "wallet"}

    # ---- defect plan (per-line) ----
    n_def = max(6, int(payments * defect_rate))
    plan = (
        ["FEE_MISMATCH"] * (n_def // 6 + 1)
        + ["SHORT_SETTLEMENT"] * (n_def // 8 + 1)
        + ["MISSING_IN_LEDGER"] * (n_def // 10 + 1)
        + ["DUPLICATE"] * (n_def // 10 + 1)
        + ["FX_DIFF"] * (n_def // 10 + 1)
    )
    rng.shuffle(plan)
    order_defect: dict[int, str] = {}
    for i, code in zip(rng.sample(range(payments), min(len(plan), payments)), plan, strict=False):
        order_defect[i] = code

    pays: list[Payment] = []
    ledger: list[LedgerEntry] = []
    truth: list[dict] = []
    buckets: dict[tuple, list[Payment]] = {}

    for i in range(payments):
        code = order_defect.get(i)
        captured = WINDOW_START + timedelta(
            days=rng.randint(0, 24), hours=rng.randint(0, 14), minutes=rng.randint(0, 59)
        )
        method = _pick_method(rng, mix)
        if code == "FX_DIFF":
            method = "card"  # an FX defect requires a cross-border card payment

        # currency: cross-border only for card-like methods
        if method in card_methods:
            pres_ccy, mid, spread = pick_presentment(rng, region, force=code == "FX_DIFF")
        else:
            pres_ccy, mid, spread = region.currency, 1.0, 0.0
        cross_border = pres_ccy != region.currency

        gross_settle = order_value(rng, p, region)
        if cross_border:
            # customer paid this in their currency; settled figure derives from it
            pres_amount = round(gross_settle / (mid * (1 - spread)), 2)
            settled_gross, eff_rate = convert(pres_amount, pres_ccy, region.currency, spread)
        else:
            pres_amount, settled_gross, eff_rate = gross_settle, gross_settle, 1.0

        fees = compute_fees(region, method, settled_gross, rates, cross_border=cross_border)
        charged_fee, charged_tax, charged_fx = fees.mdr, fees.tax, fees.fx_markup

        short_delta = 0.0
        if code == "FEE_MISMATCH":
            bump = rng.choice([0.004, 0.006, 0.009]) * settled_gross + rng.choice([0.2, 0.5, 1.0])
            charged_fee = round(fees.mdr + bump, 2)
            charged_tax = region.taxed_fee(charged_fee)
        elif code == "SHORT_SETTLEMENT":
            short_delta = round(settled_gross * rng.choice([0.01, 0.02, 0.03]) + 1, 2)
        elif code == "FX_DIFF" and cross_border:
            # gateway applied a worse rate / fatter spread than contracted
            charged_fx = round(fees.fx_markup + settled_gross * rng.choice([0.01, 0.015, 0.02]), 2)
        elif code == "FX_DIFF" and not cross_border:
            code = None  # can't inject an FX defect on a domestic payment

        net = round(settled_gross - charged_fee - charged_tax - charged_fx - short_delta, 2)
        instant = rng.random() < (0.20 if region.code == "EU" else region.instant_share)
        settled = (
            _next_business_day(captured, 0, holidays) + timedelta(hours=4)
            if instant
            else _next_business_day(captured, region.settlement_cycle_days, holidays)
        )

        card_net = rng.choice(CARD_NETWORKS) if method == "card" else None
        pay = Payment(
            payment_id=f"pay_{_rid(rng, 14)}",
            order_id=f"order_{_rid(rng, 14)}",
            order_receipt=f"RCPT-{region.code}-{100000 + i}",
            rrn=f"{rng.randint(10**11, 10**12 - 1)}",
            settlement_ref="", settlement_id="",
            kind="payment", method=method,
            card_network=card_net,
            card_issuer=bank(rng, region_code)[0] if method == "card" else None,
            card_type=rng.choice(CARD_TYPES) if method == "card" else None,
            presentment_currency=pres_ccy, presentment_amount=pres_amount,
            settlement_currency=region.currency, fx_rate=round(eff_rate, 6),
            cross_border=cross_border,
            gross=settled_gross,
            contract_fee=fees.mdr, contract_tax=fees.tax,
            charged_fee=charged_fee, charged_tax=charged_tax, fx_markup=charged_fx,
            net=net,
            captured_at=captured, settled_at=settled,
            on_hold=False, instant=instant, dispute_id=None,
            customer_name=customer(rng, region_code), city=city(rng, region_code),
        )
        pays.append(pay)
        buckets.setdefault((settled.date(), instant), []).append(pay)

        if code != "MISSING_IN_LEDGER":
            le = LedgerEntry(
                invoice_no=f"INV-{region.code}-2026-{4000 + i}",
                invoice_date=captured, order_id=pay.order_id, order_receipt=pay.order_receipt,
                customer_name=pay.customer_name, city=pay.city,
                presentment_currency=pres_ccy, presentment_amount=pres_amount,
                settlement_currency=region.currency,
                gross=settled_gross if not cross_border else round(pres_amount * mid, 2),
                method=method, status="paid",
            )
            ledger.append(le)
            if code == "DUPLICATE":
                ledger.append(LedgerEntry(**{**le.__dict__, "invoice_no": le.invoice_no + "-DUP"}))

        if code is None and rng.random() < p.refund_rate:
            rgross = -round(settled_gross * rng.choice([1.0, 1.0, 0.5]), 2)
            refund = Payment(**{**pay.__dict__,
                                "payment_id": f"rfnd_{_rid(rng, 14)}", "kind": "refund",
                                "gross": rgross, "contract_fee": 0.0, "contract_tax": 0.0,
                                "charged_fee": 0.0, "charged_tax": 0.0, "fx_markup": 0.0,
                                "net": rgross})
            pays.append(refund)
            buckets[(settled.date(), instant)].append(refund)

        expected_net = round(settled_gross - fees.total, 2)
        impact = 0.0
        if code in ("FEE_MISMATCH", "SHORT_SETTLEMENT", "FX_DIFF"):
            impact = round(expected_net - net, 2)
        truth.append({
            "order_id": pay.order_id, "order_receipt": pay.order_receipt,
            "settlement_ref": "", "expected_code": code,
            "presentment_currency": pres_ccy, "presentment_amount": pres_amount,
            "settlement_currency": region.currency,
            "gross": settled_gross, "expected_net": expected_net, "actual_net": net,
            "injected_impact_inr": impact,   # name kept for scorer compat; it's settlement-ccy
        })

    truth_by_order = {t["order_id"]: t for t in truth}

    # ---- settlement batches + aggregated bank payouts ----
    settlements: list[Settlement] = []
    bucket_keys = sorted(buckets.keys())
    small = sorted(
        range(len(bucket_keys)),
        key=lambda bi: len([x for x in buckets[bucket_keys[bi]] if x.kind == "payment"]),
    )[: max(6, len(bucket_keys) // 3)]
    rng.shuffle(small)
    def_batches: dict[int, str] = {}
    for name in ("MISSING_PAYOUT", "TIMING_GAP", "SPLIT_PAYOUT"):
        if small:
            def_batches[small.pop()] = name

    for bi, key in enumerate(bucket_keys):
        settled_date, instant = key
        batch_pays = buckets[key]
        sid = f"setl_{_rid(rng, 14)}"
        sref = payment_ref(rng, region_code)
        created = datetime.combine(settled_date, datetime.min.time()) + timedelta(hours=1)
        settled_at = created + timedelta(hours=rng.randint(2, 8))
        for bp in batch_pays:
            bp.settlement_id, bp.settlement_ref = sid, sref
            t = truth_by_order.get(bp.order_id)
            if t:
                t["settlement_ref"] = sref

        gross_payout = round(sum(bp.net for bp in batch_pays), 2)
        tds = (round(sum(bp.gross for bp in batch_pays if bp.kind == "payment") * TDS_PCT, 2)
               if p.marketplace and region.withholding else 0.0)
        reserve = round(gross_payout * ROLLING_RESERVE_PCT, 2) if p.rolling_reserve else 0.0
        net_payout = round(gross_payout - tds - reserve, 2)

        code = def_batches.get(bi)
        bank_emitted, split_parts = True, []
        value_date = _next_business_day(settled_at, 0, holidays)
        organic_split = p.marketplace and rng.random() < 0.12

        if code == "MISSING_PAYOUT":
            bank_emitted = False
        elif code == "TIMING_GAP":
            value_date = _next_business_day(settled_at, rng.choice([7, 9, 11]), holidays)
        elif code == "SPLIT_PAYOUT":
            # a Route split missing one leg -> 2+ parts that don't sum to the payout
            k = rng.choice([3, 4])
            base = round(net_payout / k, 2)
            split_parts = [base] * (k - 2) + [round(net_payout - base * (k - 1), 2)]
        elif organic_split:
            k = rng.choice([2, 3])
            base = round(net_payout / k, 2)
            split_parts = [base] * (k - 1) + [round(net_payout - base * (k - 1), 2)]

        if code in ("MISSING_PAYOUT", "TIMING_GAP", "SPLIT_PAYOUT"):
            for bp in batch_pays:
                if bp.kind != "payment":
                    continue
                t = truth_by_order.get(bp.order_id)
                if t and t["expected_code"] is None:
                    t["expected_code"] = code
                    t["injected_impact_inr"] = bp.net if code != "TIMING_GAP" else 0.0

        settlements.append(Settlement(
            settlement_id=sid, settlement_ref=sref, currency=region.currency,
            created_at=created, settled_at=settled_at, payments=batch_pays,
            tds=tds, reserve_hold=reserve, net_payout=net_payout,
            bank_emitted=bank_emitted, bank_value_date=value_date,
            bank_rail=rng.choice(region.rails), split_parts=split_parts,
        ))

    stats = {
        "profile": profile_name, "region": region_code, "currency": region.currency,
        "merchant": merchant,
        "payments": sum(1 for x in pays if x.kind == "payment"),
        "refunds": sum(1 for x in pays if x.kind == "refund"),
        "settlement_batches": len(settlements),
        "aggregated_payouts": sum(1 for s in settlements if s.bank_emitted),
        "cross_border_payments": sum(1 for x in pays if x.cross_border and x.kind == "payment"),
        "injected_defects": sum(1 for t in truth if t["expected_code"]),
        "tax_treatment": region.tax.treatment,
    }
    return Scenario(profile_name, region_code, region.currency, merchant,
                    pays, settlements, ledger, truth, stats)

"""Build a realistic settlement scenario: payments -> settlement batches ->
aggregated bank payouts -> ledger entries, plus a ground-truth key.

Key realism vs. the CI fixture:
  * bank payouts are AGGREGATED — one bank credit per settlement batch, not one
    per transaction. Reconciliation therefore happens at the batch level
    (1 bank credit <-> many PG recon lines), matched on ``settlement_utr``.
  * MDR + GST by method, forex on international cards, T+1/T+2/instant cycles
    with weekend roll-forward, refunds, 2-cycle chargebacks with reserve hold,
    marketplace TDS + Route split payouts, rolling reserve.

Injected defects (same taxonomy the pipeline scores against):
  FEE_MISMATCH, SHORT_SETTLEMENT, MISSING_PAYOUT, TIMING_GAP, DUPLICATE,
  MISSING_IN_LEDGER, SPLIT_PAYOUT
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from .economics import (
    CARD_NETWORKS,
    CARD_TYPES,
    METHODS,
    PROFILES,
    ROLLING_RESERVE_PCT,
    TDS_PCT,
    Profile,
    compute_fees,
)
from .entities import BANKS, CITIES, brand, customer, utr

WINDOW_START = datetime(2026, 8, 1, 6, 0)


@dataclass
class Payment:
    payment_id: str
    order_id: str
    order_receipt: str
    rrn: str                       # per-payment acquirer reference
    settlement_utr: str            # batch key (assigned when settled)
    settlement_id: str
    kind: str                      # payment | refund
    method: str
    card_network: str | None
    card_issuer: str | None
    card_type: str | None
    currency: str
    is_intl: bool
    gross: float                   # rupees (negative for refund)
    contract_fee: float            # fee per the merchant's contract
    contract_tax: float
    charged_fee: float             # fee the PG actually charged (differs on FEE_MISMATCH)
    charged_tax: float
    forex_fee: float
    cross_border_fee: float
    net: float                     # gross - charged fees - short-settlement delta
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
    settlement_utr: str
    created_at: datetime
    settled_at: datetime
    payments: list[Payment]
    tds: float
    reserve_hold: float
    net_payout: float              # what the bank SHOULD credit (post TDS/reserve)
    bank_emitted: bool
    bank_value_date: datetime
    bank_rail: str
    split_parts: list[float]       # >1 entry => Route split payout
    unexplained_debit: float       # SHORT_SETTLEMENT at batch level


@dataclass
class LedgerEntry:
    invoice_no: str
    invoice_date: datetime
    order_id: str
    order_receipt: str
    customer_name: str
    city: str
    gross: float
    method: str
    status: str


@dataclass
class Scenario:
    profile: str
    merchant: str
    payments: list[Payment]
    settlements: list[Settlement]
    ledger: list[LedgerEntry]
    truth: list[dict]
    stats: dict


def _next_business_day(d: datetime, cycle: int) -> datetime:
    out = d + timedelta(days=cycle)
    while out.weekday() >= 5:  # Sat/Sun roll forward
        out += timedelta(days=1)
    return out


def _lognormal_amount(rng: random.Random, median: float, sigma: float) -> float:
    val = median * math.exp(rng.gauss(0, sigma))
    return round(max(49, min(val, median * 25)), 2)


def _pick_method(rng: random.Random, mix: dict[str, float]) -> str:
    r, acc = rng.random(), 0.0
    for m, w in mix.items():
        acc += w
        if r <= acc:
            return m
    return "upi"


def build_scenario(
    profile_name: str = "d2c-brand",
    payments: int = 500,
    seed: int = 7,
    defect_rate: float = 0.12,
) -> Scenario:
    rng = random.Random(seed)
    p: Profile = PROFILES[profile_name]
    merchant = brand(rng)

    # ---- defect plan ----
    n_def = max(6, int(payments * defect_rate))
    plan = ["FEE_MISMATCH"] * (n_def // 6 + 1)
    plan += ["SHORT_SETTLEMENT"] * (n_def // 8 + 1)
    plan += ["MISSING_IN_LEDGER"] * (n_def // 10 + 1)
    plan += ["DUPLICATE"] * (n_def // 10 + 1)
    rng.shuffle(plan)
    order_defect: dict[int, str] = {}
    for i, code in zip(rng.sample(range(payments), min(len(plan), payments)), plan, strict=False):
        order_defect[i] = code
    

    pays: list[Payment] = []
    ledger: list[LedgerEntry] = []
    truth: list[dict] = []
    # bucket payments into settlement batches keyed by (settled_date, instant)
    buckets: dict[tuple, list[Payment]] = {}

    for i in range(payments):
        code = order_defect.get(i)
        captured = WINDOW_START + timedelta(
            days=rng.randint(0, 24), hours=rng.randint(0, 14), minutes=rng.randint(0, 59)
        )
        method = _pick_method(rng, p.method_mix)
        me = METHODS[method]
        is_intl = method in ("card", "wallet") and rng.random() < me.intl_share * p.intl_multiplier
        currency = "USD" if is_intl and rng.random() < 0.5 else "INR"
        gross = _lognormal_amount(rng, p.aov_median, p.aov_sigma)
        if is_intl and currency == "USD":
            gross = round(gross / 83.0, 2) * 83.0  # keep INR-equivalent, mimic FX

        fees = compute_fees(gross, method, is_intl)
        charged_fee, charged_tax = fees.mdr, fees.gst
        short_delta = 0.0
        if code == "FEE_MISMATCH":
            charged_fee = round(fees.mdr + rng.choice([1.5, 2.0, 3.0, 5.0, 8.0]), 2)
            charged_tax = round(charged_fee * 0.18, 2)
        if code == "SHORT_SETTLEMENT":
            short_delta = rng.choice([15, 25, 40, 75, 120])

        net = round(gross - charged_fee - charged_tax - fees.forex - fees.cross_border - short_delta, 2)
        instant = rng.random() < p.instant_settlement_share
        settled = (
            _next_business_day(captured, 0) + timedelta(hours=3)
            if instant
            else _next_business_day(captured, p.settlement_cycle_days)
        )

        card_net = rng.choice(CARD_NETWORKS) if method == "card" else None
        pay = Payment(
            payment_id=f"pay_{_rid(rng, 14)}",
            order_id=f"order_{_rid(rng, 14)}",
            order_receipt=f"RCPT-{p.name[:3].upper()}-{100000 + i}",
            rrn=f"{rng.randint(10**11, 10**12 - 1)}",
            settlement_utr="",  # filled at batch time
            settlement_id="",
            kind="payment",
            method=method,
            card_network=card_net,
            card_issuer=rng.choice(BANKS)[0] if method == "card" else None,
            card_type=rng.choice(CARD_TYPES) if method == "card" else None,
            currency=currency,
            is_intl=is_intl,
            gross=gross,
            contract_fee=fees.mdr,
            contract_tax=fees.gst,
            charged_fee=charged_fee,
            charged_tax=charged_tax,
            forex_fee=fees.forex,
            cross_border_fee=fees.cross_border,
            net=net,
            captured_at=captured,
            settled_at=settled,
            on_hold=False,
            instant=instant,
            dispute_id=None,
            customer_name=customer(rng),
            city=rng.choice(CITIES),
        )
        pays.append(pay)
        buckets.setdefault((settled.date(), instant), []).append(pay)

        # ledger row (skip for MISSING_IN_LEDGER)
        if code != "MISSING_IN_LEDGER":
            le = LedgerEntry(
                invoice_no=f"INV/2026/{4000 + i}",
                invoice_date=captured,
                order_id=pay.order_id,
                order_receipt=pay.order_receipt,
                customer_name=pay.customer_name,
                city=pay.city,
                gross=gross,
                method=method,
                status="paid",
            )
            ledger.append(le)
            if code == "DUPLICATE":  # webhook double-fired -> duplicate ledger row
                ledger.append(LedgerEntry(**{**le.__dict__, "invoice_no": le.invoice_no + "-DUP"}))

        # refunds (full or partial), added to the SAME batch as a negative entry
        if code is None and rng.random() < p.refund_rate:
            rgross = -round(gross * rng.choice([1.0, 1.0, 0.5]), 2)
            _ = compute_fees(abs(rgross), method, is_intl)  # keep call for parity
            refund = Payment(
                **{
                    **pay.__dict__,
                    "payment_id": f"rfnd_{_rid(rng, 14)}",
                    "kind": "refund",
                    "gross": rgross,
                    "contract_fee": 0.0,
                    "contract_tax": 0.0,
                    "charged_fee": 0.0,
                    "charged_tax": 0.0,
                    "forex_fee": 0.0,
                    "cross_border_fee": 0.0,
                    "net": rgross,
                    "settled_at": settled,
                }
            )
            pays.append(refund)
            buckets[(settled.date(), instant)].append(refund)

        truth.append(
            {
                "order_id": pay.order_id,
                "order_receipt": pay.order_receipt,
                "settlement_utr": "",  # filled at batch time
                "expected_code": code,
                "gross": gross,
                "expected_net": round(gross - fees.total, 2),
                "actual_net": net,
                "injected_impact_inr": round((gross - fees.total) - net, 2) if code in
                ("FEE_MISMATCH", "SHORT_SETTLEMENT") else 0.0,
            }
        )

    truth_by_order = {t["order_id"]: t for t in truth}

    # ---- build settlement batches + aggregated bank payouts ----
    settlements: list[Settlement] = []
    bucket_keys = sorted(buckets.keys())
    # Batch-level defects are rare and only hit SMALL batches, so a "missing
    # payout" is a handful of orders, not a whole day's volume.
    small = sorted(
        range(len(bucket_keys)),
        key=lambda bi: len([x for x in buckets[bucket_keys[bi]] if x.kind == "payment"]),
    )[: max(6, len(bucket_keys) // 3)]
    rng.shuffle(small)
    def_batches: dict[int, str] = {}
    for code_name, want in (("MISSING_PAYOUT", 1), ("TIMING_GAP", 1), ("SPLIT_PAYOUT", 1)):
        for _ in range(want):
            if small:
                def_batches[small.pop()] = code_name

    for bi, key in enumerate(bucket_keys):
        settled_date, instant = key
        batch_pays = buckets[key]
        sid = f"setl_{_rid(rng, 14)}"
        sutr = utr(rng)
        created = datetime.combine(settled_date, datetime.min.time()) + timedelta(hours=1)
        settled_at = created + timedelta(hours=rng.randint(2, 8))
        for bp in batch_pays:
            bp.settlement_id = sid
            bp.settlement_utr = sutr
            t = truth_by_order.get(bp.order_id)
            if t:
                t["settlement_utr"] = sutr

        credit = sum(bp.net for bp in batch_pays if bp.kind == "payment")
        refunds = sum(bp.net for bp in batch_pays if bp.kind == "refund")
        gross_payout = round(credit + refunds, 2)

        tds = round(sum(bp.gross for bp in batch_pays if bp.kind == "payment") * TDS_PCT, 2) if p.marketplace else 0.0
        reserve = round(gross_payout * ROLLING_RESERVE_PCT, 2) if p.rolling_reserve else 0.0

        code = def_batches.get(bi)
        unexplained = 0.0
        bank_emitted = True
        value_date = _next_business_day(settled_at, 0)
        split_parts: list[float] = []

        net_payout = round(gross_payout - tds - reserve, 2)

        organic_split = (p.marketplace or profile_name == "marketplace") and rng.random() < 0.12

        if code == "MISSING_PAYOUT":
            bank_emitted = False
        elif code == "TIMING_GAP":
            value_date = _next_business_day(settled_at, rng.choice([7, 9, 11]))
        elif code == "SPLIT_PAYOUT":
            # a Route split where one part is dropped -> parts don't sum
            k = rng.choice([2, 3])
            base = round(net_payout / k, 2)
            split_parts = [base] * (k - 2) + [round(net_payout - base * (k - 1), 2)]  # missing one part
        elif organic_split:
            # legitimate Route split — the parts DO sum; reconciler must aggregate
            k = rng.choice([2, 3])
            base = round(net_payout / k, 2)
            split_parts = [base] * (k - 1) + [round(net_payout - base * (k - 1), 2)]

        # mark real batch-defect codes onto each payment's truth row
        if code in ("MISSING_PAYOUT", "TIMING_GAP", "SPLIT_PAYOUT"):
            for bp in batch_pays:
                if bp.kind != "payment":
                    continue
                t = truth_by_order.get(bp.order_id)
                if t and t["expected_code"] is None:
                    t["expected_code"] = code
                    t["injected_impact_inr"] = bp.net if code != "TIMING_GAP" else 0.0

        settlements.append(
            Settlement(
                settlement_id=sid,
                settlement_utr=sutr,
                created_at=created,
                settled_at=settled_at,
                payments=batch_pays,
                tds=tds,
                reserve_hold=reserve,
                net_payout=net_payout,
                bank_emitted=bank_emitted,
                bank_value_date=value_date,
                bank_rail=rng.choice(["NEFT", "NEFT", "RTGS", "IMPS"]),
                split_parts=split_parts,
                unexplained_debit=unexplained,
            )
        )

    injected = sum(1 for t in truth if t["expected_code"])
    stats = {
        "profile": profile_name,
        "merchant": merchant,
        "payments": len([p for p in pays if p.kind == "payment"]),
        "refunds": len([p for p in pays if p.kind == "refund"]),
        "settlement_batches": len(settlements),
        "aggregated_payouts": sum(1 for s in settlements if s.bank_emitted),
        "injected_defects": injected,
        "intl_payments": sum(1 for p in pays if p.is_intl),
    }
    return Scenario(profile_name, merchant, pays, settlements, ledger, truth, stats)


def _rid(rng: random.Random, n: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(rng.choice(alphabet) for _ in range(n))

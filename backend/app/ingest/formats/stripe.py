"""Stripe payout-reconciliation report (balance transactions) -> NormalizedTxn.

Used for US / EU merchants. Grouping key is ``automatic_payout_id`` (Stripe's
per-payout batch id); the settlement currency is ``currency``; the customer's
currency + amount + fx rate are on the same row for cross-border charges.
"""

from __future__ import annotations

from datetime import datetime

import polars as pl

from ...models import NormalizedTxn, Source
from ._locale import parse_amount


def looks_like(header: list[str]) -> bool:
    h = {c.strip().lower() for c in header}
    return "balance_transaction_id" in h or (
        {"automatic_payout_id", "net", "currency"} <= h
    ) or {"reporting_category", "customer_facing_currency"} <= h


def _dt(v) -> datetime | None:
    if not v:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt)
        except ValueError:
            continue
    return None


def parse(path: str, batch_id: str) -> list[NormalizedTxn]:
    df = pl.read_csv(path, infer_schema_length=0)
    lower = {c.lower(): c for c in df.columns}

    def col(*names):
        for n in names:
            if n in lower:
                return lower[n]
        return None

    c_id = col("balance_transaction_id", "id")
    c_type = col("type", "reporting_category")
    c_gross = col("gross", "amount")
    c_fee = col("fee")
    c_net = col("net")
    c_ccy = col("currency")
    c_cust_amt = col("customer_facing_amount", "presentment_amount")
    c_cust_ccy = col("customer_facing_currency", "presentment_currency")
    c_created = col("created_utc", "created", "created_at")
    c_avail = col("available_on_utc", "available_on")
    c_payout = col("automatic_payout_id", "payout_id")
    c_method = col("payment_method_type", "method")
    c_order = col("order_id")
    c_receipt = col("order_receipt")
    c_fx = col("fx_rate")

    out: list[NormalizedTxn] = []
    for i, row in enumerate(df.iter_rows(named=True)):
        kind = "refund" if "refund" in str(row.get(c_type, "")).lower() else "payment"
        gross = parse_amount(row.get(c_gross))
        fee = abs(parse_amount(row.get(c_fee)))
        net = parse_amount(row.get(c_net)) if c_net else round(gross - fee, 2)
        ccy = str(row.get(c_ccy) or "USD").upper()
        cust_ccy = str(row.get(c_cust_ccy) or ccy).upper()
        fx = parse_amount(row.get(c_fx)) if c_fx else 1.0
        cust_amt = parse_amount(row.get(c_cust_amt)) if c_cust_amt else None
        cross = cust_ccy != ccy

        out.append(
            NormalizedTxn(
                batch_id=batch_id,
                source=Source.PG,
                raw_record_id=f"pg:{i}",
                external_id=str(row.get(c_order) or row.get(c_receipt) or row.get(c_id) or "") or None,
                utr=str(row.get(c_payout) or "").strip() or None,
                settlement_id=str(row.get(c_payout) or "").strip() or None,
                method=str(row.get(c_method) or "").strip().lower() or None,
                kind=kind,
                currency=ccy,
                presentment_currency=cust_ccy if cross else None,
                presentment_amount=cust_amt if cross else None,
                fx_rate=fx if cross else None,
                amount_gross=gross,
                fee=fee,
                tax=0.0,
                amount_net=net,
                txn_date=_dt(row.get(c_created)),
                settlement_date=_dt(row.get(c_avail)),
                narration=(
                    f"{row.get(c_type, '')} "
                    + (f"fx {cust_ccy}->{ccy} @{fx}" if cust_ccy != ccy else "")
                ).strip(),
                status="settled",
            )
        )
    return out

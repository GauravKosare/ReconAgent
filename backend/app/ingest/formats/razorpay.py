"""Razorpay Settlement Recon Report -> NormalizedTxn (source = PG).

Real report quirks handled: amounts in paise (integer subunits), unix
timestamps, ``settlement_utr`` shared across every line in a settlement batch,
refunds carried as ``type=refund`` with the value in ``debit``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from ...models import NormalizedTxn, Source


def _rupees(paise) -> float:
    try:
        return round(int(float(paise)) / 100.0, 2)
    except (TypeError, ValueError):
        return 0.0


def _dt(unix) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(float(unix)), tz=UTC).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def looks_like(header: list[str]) -> bool:
    h = {c.strip().lower() for c in header}
    return {"settlement_utr", "entity_id"} <= h or {"settlement_id", "credit", "debit"} <= h


def parse(path: str, batch_id: str) -> list[NormalizedTxn]:
    df = pl.read_csv(path, infer_schema_length=2000)
    lower = {c.lower(): c for c in df.columns}

    def col(*names: str) -> str | None:
        for n in names:
            if n in lower:
                return lower[n]
        return None

    c_entity = col("entity_id", "payment_id", "transaction_entity")
    c_type = col("type")
    c_debit, c_credit, c_amount = col("debit"), col("credit"), col("amount")
    c_fee, c_tax = col("fee"), col("tax")
    c_created, c_settled = col("created_at"), col("settled_at")
    c_setl_id = col("settlement_id")
    c_setl_utr = col("settlement_utr", "utr")
    c_order = col("order_id")
    c_receipt = col("order_receipt")
    c_method = col("method")

    out: list[NormalizedTxn] = []
    for i, row in enumerate(df.iter_rows(named=True)):
        kind = str(row.get(c_type, "payment") or "payment").lower()
        gross = _rupees(row.get(c_amount))
        fee = _rupees(row.get(c_fee))
        tax = _rupees(row.get(c_tax))
        if kind == "refund":
            net = -_rupees(row.get(c_debit)) if c_debit else -gross
            gross = -gross
        else:
            net = _rupees(row.get(c_credit)) if c_credit else round(gross - fee - tax, 2)

        out.append(
            NormalizedTxn(
                batch_id=batch_id,
                source=Source.PG,
                raw_record_id=f"pg:{i}",
                external_id=str(row.get(c_order) or row.get(c_receipt) or row.get(c_entity) or "") or None,
                utr=str(row.get(c_setl_utr) or "").strip() or None,
                settlement_id=str(row.get(c_setl_id) or "").strip() or None,
                method=str(row.get(c_method) or "").strip().lower() or None,
                kind=kind,
                currency=str(row.get(col("currency") or "currency") or "INR").strip() or "INR",
                amount_gross=gross,
                fee=fee,
                tax=tax,
                amount_net=net,
                txn_date=_dt(row.get(c_created)),
                settlement_date=_dt(row.get(c_settled)),
                narration=str(row.get("description", "") or ""),
                status="settled",
            )
        )
    return out

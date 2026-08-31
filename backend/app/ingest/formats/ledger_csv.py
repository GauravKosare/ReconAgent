"""Internal ledger export (Zoho Books / Tally style) -> NormalizedTxn.

The ledger has no UTR — it joins to the PG report on the order id / receipt
number, so both are kept in ``external_id`` (primary) with the receipt as a
secondary lookup carried in ``narration``.
"""

from __future__ import annotations

from datetime import datetime

import polars as pl

from ...models import NormalizedTxn, Source

_ALIASES = {
    "external_id": ["order id", "order_id", "reference number", "reference_number",
                    "invoice number", "invoice_number", "invoice id"],
    "receipt": ["reference number", "reference_number", "order receipt", "receipt"],
    "amount": ["total", "amount", "invoice amount", "grand total", "invoiced amount"],
    "date": ["invoice date", "invoice_date", "date", "transaction date"],
    "customer": ["customer name", "customer_name", "customer", "contact name"],
    "method": ["payment mode", "payment_mode", "payment method", "mode"],
    "status": ["invoice status", "status", "payment status"],
}


def looks_like(header: list[str]) -> bool:
    h = {c.strip().lower() for c in header}
    return "invoice number" in h or ("order id" in h and "total" in h) or "invoice date" in h


def _f(v) -> float:
    try:
        return round(float(str(v).replace(",", "").replace("₹", "").strip()), 2)
    except (TypeError, ValueError):
        return 0.0


def _d(v) -> datetime | None:
    if not v:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y"):
        try:
            return datetime.strptime(str(v).strip()[:11].strip(), fmt)
        except ValueError:
            continue
    return None


def parse(path: str, batch_id: str) -> list[NormalizedTxn]:
    df = pl.read_csv(path, infer_schema_length=2000)
    lower = {c.strip().lower(): c for c in df.columns}

    def pick(row, key):
        for a in _ALIASES[key]:
            if a in lower and row.get(lower[a]) not in (None, "", "nan"):
                return row[lower[a]]
        return None

    out: list[NormalizedTxn] = []
    for i, row in enumerate(df.iter_rows(named=True)):
        gross = _f(pick(row, "amount"))
        oid = pick(row, "external_id")
        receipt = pick(row, "receipt")
        out.append(
            NormalizedTxn(
                batch_id=batch_id,
                source=Source.LEDGER,
                raw_record_id=f"ledger:{i}",
                external_id=str(oid) if oid else (str(receipt) if receipt else None),
                utr=None,
                method=str(pick(row, "method") or "").strip().lower() or None,
                amount_gross=gross,
                amount_net=gross,
                txn_date=_d(pick(row, "date")),
                narration=" ".join(
                    str(x) for x in (pick(row, "customer"), receipt) if x
                ).strip(),
                status=str(pick(row, "status") or "").strip().lower(),
            )
        )
    return out

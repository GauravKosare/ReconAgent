"""Internal ledger export (Zoho Books / Tally style) -> NormalizedTxn.

The ledger has no UTR — it joins to the PG report on the order id / receipt
number, so both are kept in ``external_id`` (primary) with the receipt as a
secondary lookup carried in ``narration``.
"""

from __future__ import annotations

import polars as pl

from ...models import NormalizedTxn, Source
from ._locale import parse_amount, parse_date

_ALIASES = {
    "external_id": ["order id", "order_id", "reference number", "reference_number",
                    "invoice number", "invoice_number", "invoice id"],
    "receipt": ["reference number", "reference_number", "order receipt", "receipt"],
    "amount": ["total", "amount", "invoice amount", "grand total", "invoiced amount"],
    "date": ["invoice date", "invoice_date", "date", "transaction date"],
    "customer": ["customer name", "customer_name", "customer", "contact name"],
    "method": ["payment mode", "payment_mode", "payment method", "mode"],
    "status": ["invoice status", "status", "payment status"],
    "presentment_ccy": ["presentment currency", "customer currency"],
    "presentment_amt": ["presentment amount", "customer amount"],
    "currency": ["currency", "settlement currency", "base currency"],
}


def looks_like(header: list[str]) -> bool:
    h = {c.strip().lower() for c in header}
    return "invoice number" in h or ("order id" in h and "total" in h) or "invoice date" in h


def _f(v) -> float:
    return round(parse_amount(v), 2)


def _d(v, pref="dmy"):
    return parse_date(v, pref)


def _sep(path: str) -> str:
    with open(path, encoding='utf-8', errors='ignore') as fh:
        head = fh.readline()
    return ';' if head.count(';') > head.count(',') else ','


def parse(path: str, batch_id: str) -> list[NormalizedTxn]:
    df = pl.read_csv(path, separator=_sep(path), infer_schema_length=0)
    lower = {c.strip().lower(): c for c in df.columns}

    def pick(row, key):
        for a in _ALIASES[key]:
            if a in lower and row.get(lower[a]) not in (None, "", "nan"):
                return row[lower[a]]
        return None

    # US ledgers use mm/dd/yyyy; infer from the settlement currency column
    ccy_col = next((lower[a] for a in _ALIASES["currency"] if a in lower), None)
    sample_ccy = ""
    if ccy_col:
        for r in df.iter_rows(named=True):
            if r.get(ccy_col):
                sample_ccy = str(r[ccy_col]).upper()
                break
    date_pref = "mdy" if sample_ccy == "USD" else "dmy"

    out: list[NormalizedTxn] = []
    for i, row in enumerate(df.iter_rows(named=True)):
        gross = _f(pick(row, "amount"))
        oid = pick(row, "external_id")
        receipt = pick(row, "receipt")
        pres_ccy = str(pick(row, "presentment_ccy") or "").strip().upper()
        settle_ccy = str(pick(row, "currency") or "").strip().upper()
        out.append(
            NormalizedTxn(
                batch_id=batch_id,
                source=Source.LEDGER,
                raw_record_id=f"ledger:{i}",
                external_id=str(oid) if oid else (str(receipt) if receipt else None),
                utr=None,
                method=str(pick(row, "method") or "").strip().lower() or None,
                currency=settle_ccy or "INR",
                amount_gross=gross,
                amount_net=gross,
                txn_date=_d(pick(row, "date"), date_pref),
                narration=" ".join(
                    str(x) for x in (pick(row, "customer"), receipt,
                                     f"[{pres_ccy}]" if pres_ccy and pres_ccy != settle_ccy else "")
                    if x
                ).strip(),
                status=str(pick(row, "status") or "").strip().lower(),
            )
        )
    return out

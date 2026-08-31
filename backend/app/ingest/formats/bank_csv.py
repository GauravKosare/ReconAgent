"""Bank statement CSV (HDFC / ICICI / Axis / Chase-style US / generic) ->
NormalizedTxn.

AGGREGATED payout rows: one bank credit per PG settlement batch (a few for Route
splits). The settlement reference (UTR / ACH trace / E2E id) is pulled from the
ref column if present, else from the narration. Amounts and dates are parsed
locale-tolerantly (US/IN `1,234.56` vs EU `1.234,56`).
"""

from __future__ import annotations

import re

import polars as pl

from ...models import NormalizedTxn, Source
from ._locale import parse_amount, parse_date

_ALIASES = {
    "date": ["value dt", "value date", "txn date", "transaction date", "date",
             "posting date", "tran date", "booking date"],
    "narration": ["narration", "transaction remarks", "particulars", "description",
                  "remarks", "transaction description", "details / description"],
    "ref": ["chq./ref.no.", "chq/ref number", "ref no", "reference no", "cheque number",
            "chq no", "ref no.", "utr", "utr no", "utr number", "trace number", "reference"],
    "credit": ["deposit amt.", "deposit amount (inr )", "deposit amount", "credit",
               "cr amount", "credit amount", "deposit", "credit amount (eur)"],
    "debit": ["withdrawal amt.", "withdrawal amount (inr )", "withdrawal amount",
              "debit", "dr amount", "debit amount"],
    # US Chase-style single signed Amount column + Details=DEBIT/CREDIT
    "amount": ["amount"],
    "sign": ["details", "type", "cr/dr", "dr/cr"],
    "balance": ["closing balance", "balance (inr )", "balance", "running balance"],
}

_REF_RE = re.compile(
    r"\b([0-9]{12}[A-Za-z0-9-]{0,4}"            # IN UTR
    r"|[0-9]{15}"                                 # US ACH trace
    r"|E2E[A-Z0-9]{6,}"                           # EU End-to-End id
    r"|[0-9]{7,10}[a-z][0-9][a-z][0-9]{2,3})\b"   # Razorpay alnum
)


def looks_like(header: list[str]) -> bool:
    h = {c.strip().lower() for c in header}
    return (
        {"narration", "closing balance"} <= h
        or "transaction remarks" in h
        or ("value date" in h and ("deposit amount" in h or "credit" in h))
        or {"details", "posting date", "amount", "balance"} <= h   # US Chase-style
    )


def _extract_ref(ref: str, narration: str) -> str | None:
    for text in (ref, narration):
        if not text:
            continue
        m = _REF_RE.search(str(text))
        if m:
            return m.group(1).split("-")[0]
    return str(ref).strip() or None


def _sep(path: str) -> str:
    with open(path, encoding='utf-8', errors='ignore') as fh:
        head = fh.readline()
    return ';' if head.count(';') > head.count(',') else ','


def parse(path: str, batch_id: str) -> list[NormalizedTxn]:
    df = pl.read_csv(path, separator=_sep(path), infer_schema_length=0, truncate_ragged_lines=True)
    lower = {c.strip().lower(): c for c in df.columns}
    us = "posting date" in lower or "details" in lower
    dmy = not us
    header_blob = " ".join(lower).lower()
    currency = (
        "INR" if "(inr" in header_blob else
        "EUR" if "(eur" in header_blob else
        "USD" if us else None
    )

    def pick(row, key):
        for a in _ALIASES[key]:
            if a in lower and row.get(lower[a]) not in (None, ""):
                return row[lower[a]]
        return None

    out: list[NormalizedTxn] = []
    for i, row in enumerate(df.iter_rows(named=True)):
        credit = parse_amount(pick(row, "credit"))
        debit = parse_amount(pick(row, "debit"))
        if credit == 0 and debit == 0:
            amt = parse_amount(pick(row, "amount"))
            sign = str(pick(row, "sign") or "").upper()
            if amt:
                if "DEBIT" in sign or amt < 0:
                    debit = abs(amt)
                else:
                    credit = abs(amt)
        if credit == 0 and debit == 0:
            continue

        narr = str(pick(row, "narration") or "")
        ref = str(pick(row, "ref") or "")
        amount = credit if credit else -debit
        out.append(
            NormalizedTxn(
                batch_id=batch_id,
                source=Source.BANK,
                raw_record_id=f"bank:{i}",
                external_id=None,
                utr=_extract_ref(ref, narr),
                currency=currency or "INR",
                kind="payment" if credit else "adjustment",
                amount_gross=abs(amount),
                amount_net=amount,
                txn_date=parse_date(pick(row, "date"), "dmy" if dmy else "mdy"),
                settlement_date=parse_date(pick(row, "date"), "dmy" if dmy else "mdy"),
                narration=narr,
                status="credited" if credit else "debited",
            )
        )
    return out

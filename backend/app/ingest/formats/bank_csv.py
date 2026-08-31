"""Bank statement CSV (HDFC / ICICI / Axis / generic) -> NormalizedTxn.

These are AGGREGATED payout rows: one bank credit per PG settlement batch (or a
few, for Route splits). The settlement UTR is pulled from the ref/cheque column
if present, else from the narration.
"""

from __future__ import annotations

import re
from datetime import datetime

import polars as pl

from ...models import NormalizedTxn, Source

_ALIASES = {
    "date": ["value dt", "value date", "txn date", "transaction date", "date",
             "posting date", "tran date"],
    "narration": ["narration", "transaction remarks", "particulars", "description",
                  "remarks", "transaction description"],
    "ref": ["chq./ref.no.", "chq/ref number", "ref no", "reference no", "cheque number",
            "chq no", "ref no.", "utr", "utr no", "utr number"],
    "credit": ["deposit amt.", "deposit amount (inr )", "deposit amount", "credit",
               "cr amount", "credit amount", "deposit"],
    "debit": ["withdrawal amt.", "withdrawal amount (inr )", "withdrawal amount",
              "debit", "dr amount"],
    "balance": ["closing balance", "balance (inr )", "balance", "running balance"],
}

_UTR_RE = re.compile(r"\b([0-9]{12}[A-Za-z0-9-]{0,4}|[0-9]{9}[a-z][0-9][a-z][0-9]{3})\b")


def looks_like(header: list[str]) -> bool:
    h = {c.strip().lower() for c in header}
    return (
        {"narration", "closing balance"} <= h
        or "transaction remarks" in h
        or ("value date" in h and ("deposit amount" in h or "credit" in h))
    )


def _f(v) -> float:
    try:
        s = str(v).replace(",", "").strip()
        return round(float(s), 2) if s and s not in ("-", "0.00") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _d(v) -> datetime | None:
    if not v:
        return None
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt)
        except ValueError:
            continue
    return None


def _extract_utr(ref: str, narration: str) -> str | None:
    for text in (ref, narration):
        if not text:
            continue
        m = _UTR_RE.search(str(text))
        if m:
            return m.group(1).split("-")[0]
    return str(ref).strip() or None


def parse(path: str, batch_id: str) -> list[NormalizedTxn]:
    df = pl.read_csv(path, infer_schema_length=2000, truncate_ragged_lines=True)
    lower = {c.strip().lower(): c for c in df.columns}

    def pick(row, key):
        for a in _ALIASES[key]:
            if a in lower and row.get(lower[a]) not in (None, ""):
                return row[lower[a]]
        return None

    out: list[NormalizedTxn] = []
    for i, row in enumerate(df.iter_rows(named=True)):
        credit = _f(pick(row, "credit"))
        debit = _f(pick(row, "debit"))
        if credit == 0 and debit == 0:
            continue  # opening/closing balance line etc.
        narr = str(pick(row, "narration") or "")
        ref = str(pick(row, "ref") or "")
        amount = credit if credit else -debit
        out.append(
            NormalizedTxn(
                batch_id=batch_id,
                source=Source.BANK,
                raw_record_id=f"bank:{i}",
                external_id=None,
                utr=_extract_utr(ref, narr),
                kind="payment" if credit else "adjustment",
                amount_gross=abs(amount),
                amount_net=amount,
                txn_date=_d(pick(row, "date")),
                settlement_date=_d(pick(row, "date")),
                narration=narr,
                status="credited" if credit else "debited",
            )
        )
    return out

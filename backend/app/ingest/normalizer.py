"""Stage 0 — parse heterogeneous source files into the common transaction schema.

Each source has its own column vocabulary. Column maps below are deliberately
generous (many aliases) so real-world exports drop in with minimal tweaking.
Raw rows are stored verbatim elsewhere; this module only produces NormalizedTxn.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import polars as pl

from ..models import NormalizedTxn, Source

# Candidate column names per logical field, per source.
COLUMN_MAP: dict[Source, dict[str, list[str]]] = {
    Source.LEDGER: {
        "external_id": ["order_id", "invoice_id", "reference", "txn_id"],
        "utr": ["utr", "rrn", "bank_ref"],
        "amount_gross": ["amount", "gross_amount", "total", "invoice_amount"],
        "txn_date": ["date", "txn_date", "invoice_date", "created_at"],
        "narration": ["description", "narration", "memo", "customer"],
        "status": ["status", "state"],
    },
    Source.PG: {
        "external_id": ["payment_id", "transaction_id", "pg_txn_id", "order_id"],
        "utr": ["utr", "rrn", "bank_reference", "acquirer_ref"],
        "amount_gross": ["amount", "gross_amount", "captured_amount"],
        "fee": ["fee", "commission", "mdr", "pg_fee"],
        "tax": ["tax", "gst", "gst_amount"],
        "amount_net": ["net_amount", "settlement_amount", "payout_amount", "credit_amount"],
        "txn_date": ["created_at", "captured_at", "txn_date", "transaction_date"],
        "settlement_date": ["settled_at", "settlement_date", "payout_date"],
        "narration": ["description", "notes", "method"],
        "status": ["status", "state"],
    },
    Source.BANK: {
        "utr": ["utr", "rrn", "ref_no", "reference_number", "cheque_ref"],
        "amount_gross": ["credit", "amount", "deposit", "credit_amount"],
        "amount_net": ["credit", "amount", "deposit", "credit_amount"],
        "txn_date": ["date", "value_date", "txn_date", "posting_date"],
        "settlement_date": ["date", "value_date", "posting_date"],
        "narration": ["narration", "description", "particulars", "remarks"],
        "status": ["status"],
    },
}


def _pick(row: dict[str, Any], aliases: list[str]) -> Any:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in aliases:
        if alias in lower and lower[alias] not in (None, "", "nan"):
            return lower[alias]
    return None


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace(",", "").replace("₹", "").replace("INR", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _to_date(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(value).strip()[: len(fmt) + 2], fmt)
        except ValueError:
            continue
    return None


def normalize_file(
    path: str,
    source: Source,
    batch_id: str,
    raw_ids: list[str] | None = None,
) -> list[NormalizedTxn]:
    """Read a CSV/XLSX file and return NormalizedTxn rows.

    `raw_ids` (optional) aligns row i to its stored raw_records _id.
    """

    df = pl.read_csv(path, infer_schema_length=1000, try_parse_dates=False)
    cmap = COLUMN_MAP[source]
    out: list[NormalizedTxn] = []

    for i, row in enumerate(df.iter_rows(named=True)):
        gross = _to_float(_pick(row, cmap.get("amount_gross", [])))
        fee = _to_float(_pick(row, cmap.get("fee", [])))
        tax = _to_float(_pick(row, cmap.get("tax", [])))
        net_raw = _pick(row, cmap.get("amount_net", []))
        net = _to_float(net_raw) if net_raw is not None else round(gross - fee - tax, 2)

        out.append(
            NormalizedTxn(
                batch_id=batch_id,
                source=source,
                raw_record_id=raw_ids[i] if raw_ids and i < len(raw_ids) else f"{source.value}:{i}",
                external_id=(_pick(row, cmap.get("external_id", [])) or None)
                and str(_pick(row, cmap.get("external_id", []))),
                utr=(_pick(row, cmap.get("utr", [])) or None)
                and str(_pick(row, cmap.get("utr", []))).strip(),
                amount_gross=gross,
                fee=fee,
                tax=tax,
                amount_net=net,
                txn_date=_to_date(_pick(row, cmap.get("txn_date", []))),
                settlement_date=_to_date(_pick(row, cmap.get("settlement_date", []))),
                narration=str(_pick(row, cmap.get("narration", [])) or "").strip(),
                status=str(_pick(row, cmap.get("status", [])) or "").strip(),
            )
        )
    return out

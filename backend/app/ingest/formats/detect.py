"""Sniff a statement file's format and dispatch to the right parser."""

from __future__ import annotations

import csv
from pathlib import Path

from ...models import NormalizedTxn, Source
from . import bank_camt, bank_csv, bank_mt940, ledger_csv, razorpay


def _header(path: str) -> list[str]:
    with open(path, encoding="utf-8", errors="ignore", newline="") as fh:
        try:
            return next(csv.reader(fh))
        except StopIteration:
            return []


def detect_format(path: str) -> str:
    p = Path(path)
    text_head = p.read_text(encoding="utf-8", errors="ignore")[:4000]
    ext = p.suffix.lower()

    if ext in (".xml",) or bank_camt.looks_like(text_head):
        return "bank_camt"
    if ext in (".mt940", ".sta", ".txt") or bank_mt940.looks_like(text_head):
        return "bank_mt940"

    if ext in (".csv", ".tsv", ""):
        header = _header(path)
        if razorpay.looks_like(header):
            return "razorpay"
        if bank_csv.looks_like(header):
            return "bank_csv"
        if ledger_csv.looks_like(header):
            return "ledger_csv"
    raise ValueError(f"could not detect statement format for {path}")


_PARSERS = {
    "razorpay": (Source.PG, lambda path, bid: razorpay.parse(path, bid)),
    "ledger_csv": (Source.LEDGER, lambda path, bid: ledger_csv.parse(path, bid)),
    "bank_csv": (Source.BANK, lambda path, bid: bank_csv.parse(path, bid)),
    "bank_mt940": (Source.BANK, lambda path, bid: bank_mt940.parse_text(
        Path(path).read_text(encoding="utf-8", errors="ignore"), bid)),
    "bank_camt": (Source.BANK, lambda path, bid: bank_camt.parse_text(
        Path(path).read_text(encoding="utf-8", errors="ignore"), bid)),
}


def detect_and_parse(path: str, batch_id: str) -> tuple[Source, str, list[NormalizedTxn]]:
    fmt = detect_format(path)
    source, fn = _PARSERS[fmt]
    return source, fmt, fn(path, batch_id)

"""SWIFT MT940 statement -> NormalizedTxn (source = BANK).

Parses the tags we care about:
  :25:  account id
  :61:  statement line  — value date, entry date, D/C mark, amount, ref
  :86:  information to account owner (narration), follows its :61:
"""

from __future__ import annotations

import re
from datetime import datetime

from ...models import NormalizedTxn, Source

_L61 = re.compile(
    r"^:61:(?P<vdate>\d{6})(?P<edate>\d{4})?(?P<mark>[CD]|RC|RD)(?P<amount>[\d,]+)"
    r"(?P<code>[A-Z][A-Z0-9]{3})(?P<ref>[^/]*)(?://(?P<bankref>.*))?$"
)
_UTR = re.compile(r"([0-9]{9,14}[A-Za-z0-9]{0,4})")


def looks_like(text: str) -> bool:
    return ":61:" in text and (":20:" in text or ":25:" in text)


def _amt(s: str) -> float:
    return round(float(s.replace(",", ".")), 2)


def _vdate(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%y%m%d")
    except ValueError:
        return None


_CCY60 = re.compile(r":6[02]F:[CD]\d{6}([A-Z]{3})")


def parse_text(text: str, batch_id: str) -> list[NormalizedTxn]:
    lines = text.replace("\r\n", "\n").split("\n")
    ccy_m = _CCY60.search(text)
    currency = ccy_m.group(1) if ccy_m else "EUR"
    out: list[NormalizedTxn] = []
    i = 0
    idx = 0
    while i < len(lines):
        line = lines[i].strip()
        m = _L61.match(line)
        if not m:
            i += 1
            continue
        narration = ""
        if i + 1 < len(lines) and lines[i + 1].startswith(":86:"):
            narration = lines[i + 1][4:].strip()
            i += 1
        is_credit = m.group("mark") in ("C", "RC")
        amount = _amt(m.group("amount"))
        ref = (m.group("bankref") or m.group("ref") or "").strip()
        utr_m = _UTR.search(ref) or _UTR.search(narration)
        out.append(
            NormalizedTxn(
                batch_id=batch_id,
                source=Source.BANK,
                raw_record_id=f"bank:{idx}",
                utr=(utr_m.group(1).split("-")[0] if utr_m else ref) or None,
                currency=currency,
                kind="payment" if is_credit else "adjustment",
                amount_gross=amount,
                amount_net=amount if is_credit else -amount,
                txn_date=_vdate(m.group("vdate")),
                settlement_date=_vdate(m.group("vdate")),
                narration=narration,
                status="credited" if is_credit else "debited",
            )
        )
        idx += 1
        i += 1
    return out

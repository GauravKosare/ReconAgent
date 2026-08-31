"""ISO 20022 camt.053 bank statement (XML) -> NormalizedTxn (source = BANK)."""

from __future__ import annotations

import re
from datetime import datetime
from xml.etree import ElementTree as ET

from ...models import NormalizedTxn, Source

_UTR = re.compile(r"([0-9]{9,14}[A-Za-z0-9]{0,4})")


def looks_like(text: str) -> bool:
    return "camt.053" in text or ("<Ntry>" in text and "<CdtDbtInd>" in text)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(el, name):
    for child in el.iter():
        if _local(child.tag) == name:
            return child
    return None


def _text(el, name) -> str:
    f = _find(el, name)
    if f is None:
        return ""
    if (f.text or "").strip():
        return f.text.strip()
    # value may be in a nested element (e.g. <ValDt><Dt>2026-08-03</Dt></ValDt>)
    for sub in f.iter():
        if sub is not f and (sub.text or "").strip():
            return sub.text.strip()
    return ""


def parse_text(text: str, batch_id: str) -> list[NormalizedTxn]:
    root = ET.fromstring(text)
    out: list[NormalizedTxn] = []
    idx = 0
    for ntry in (e for e in root.iter() if _local(e.tag) == "Ntry"):
        cd = _text(ntry, "CdtDbtInd")
        is_credit = cd == "CRDT"
        try:
            amount = round(float(_text(ntry, "Amt")), 2)
        except ValueError:
            continue
        vdt = _text(ntry, "ValDt") or _text(ntry, "BookgDt")
        acsvcr = _text(ntry, "AcctSvcrRef")
        txid = _text(ntry, "TxId")
        e2e = _text(ntry, "EndToEndId")
        rmt = _text(ntry, "Ustrd")
        ref = txid or acsvcr or e2e
        m = _UTR.search(ref) or _UTR.search(rmt)
        try:
            d = datetime.strptime(vdt[:10], "%Y-%m-%d")
        except ValueError:
            d = None
        out.append(
            NormalizedTxn(
                batch_id=batch_id,
                source=Source.BANK,
                raw_record_id=f"bank:{idx}",
                utr=(m.group(1).split("-")[0] if m else ref) or None,
                kind="payment" if is_credit else "adjustment",
                amount_gross=amount,
                amount_net=amount if is_credit else -amount,
                txn_date=d,
                settlement_date=d,
                narration=rmt,
                status="credited" if is_credit else "debited",
            )
        )
        idx += 1
    return out

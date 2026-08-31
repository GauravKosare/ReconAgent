"""Render a Scenario into real-world file formats.

  razorpay_recon   Razorpay Settlement Recon Report (CSV; paise; unix ts)
  bank_mt940       SWIFT MT940 statement (tag format)
  bank_camt053     ISO 20022 camt.053.001.02 (XML)
  bank_hdfc_csv    HDFC Bank statement CSV layout
  bank_icici_csv   ICICI Bank statement CSV layout
  ledger_zoho      Zoho Books "Sales by Item / Invoices" style export (CSV)
"""

from __future__ import annotations

import csv
import io
import random
from datetime import datetime
from xml.sax.saxutils import escape

from .entities import narration
from .scenario import Scenario

# ---------------------------------------------------------------- Razorpay ----

_RECON_COLS = [
    "entity_id", "type", "debit", "credit", "amount", "currency", "fee", "tax",
    "on_hold", "settled", "created_at", "settled_at", "settlement_id", "posted_at",
    "credit_type", "description", "notes", "payment_id", "settlement_utr",
    "order_id", "order_receipt", "method", "card_network", "card_issuer",
    "card_type", "dispute_id",
]


def _paise(x: float) -> int:
    return int(round(x * 100))


def _ts(dt: datetime | None) -> str:
    return "" if dt is None else str(int(dt.timestamp()))


def razorpay_recon(sc: Scenario) -> str:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=_RECON_COLS)
    w.writeheader()
    for p in sorted(sc.payments, key=lambda x: x.settled_at):
        is_refund = p.kind == "refund"
        amt = abs(p.gross)
        # Razorpay folds the international transaction fee into `fee`, so that
        # net == amount - fee - tax always holds on the recon report.
        fee_total = round(p.charged_fee + p.forex_fee + p.cross_border_fee, 2)
        w.writerow(
            {
                "entity_id": p.payment_id,
                "type": "refund" if is_refund else "payment",
                "debit": _paise(amt) if is_refund else 0,
                "credit": 0 if is_refund else _paise(p.net),
                "amount": _paise(amt),
                "currency": p.currency,
                "fee": _paise(fee_total),
                "tax": _paise(p.charged_tax),
                "on_hold": str(p.on_hold),
                "settled": "True",
                "created_at": _ts(p.captured_at),
                "settled_at": _ts(p.settled_at),
                "settlement_id": p.settlement_id,
                "posted_at": "",
                "credit_type": "default",
                "description": ("Refund" if is_refund else "Payment")
                + (" (International)" if p.is_intl else "")
                + f" via {p.method.upper()}",
                "notes": "",
                "payment_id": p.payment_id if is_refund else "",
                "settlement_utr": p.settlement_utr,
                "order_id": p.order_id,
                "order_receipt": p.order_receipt,
                "method": p.method,
                "card_network": p.card_network or "",
                "card_issuer": p.card_issuer or "",
                "card_type": p.card_type or "",
                "dispute_id": p.dispute_id or "",
            }
        )
    return out.getvalue()


# ----------------------------------------------------------------- Ledger ----

_LEDGER_COLS = [
    "Invoice Number", "Invoice Date", "Order ID", "Reference Number",
    "Customer Name", "Place of Supply", "Invoice Status", "Payment Mode",
    "Total", "Currency",
]


def ledger_zoho(sc: Scenario) -> str:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=_LEDGER_COLS)
    w.writeheader()
    for le in sc.ledger:
        w.writerow(
            {
                "Invoice Number": le.invoice_no,
                "Invoice Date": le.invoice_date.strftime("%d/%m/%Y"),
                "Order ID": le.order_id,
                "Reference Number": le.order_receipt,
                "Customer Name": le.customer_name,
                "Place of Supply": le.city,
                "Invoice Status": "Paid",
                "Payment Mode": le.method.title(),
                "Total": f"{le.gross:.2f}",
                "Currency": "INR",
            }
        )
    return out.getvalue()


# --------------------------------------------------------- bank: payout rows ----

def _payout_lines(sc: Scenario) -> list[dict]:
    """One or more bank credit lines per emitted settlement (Route splits ->
    several)."""
    rng = random.Random(hash(sc.merchant) & 0xFFFF)
    rows: list[dict] = []
    for s in sc.settlements:
        if not s.bank_emitted:
            continue
        amounts = s.split_parts or [s.net_payout]
        for j, amt in enumerate(amounts):
            ref = s.settlement_utr if j == 0 else f"{s.settlement_utr}-{j+1}"
            rows.append(
                {
                    "value_date": s.bank_value_date,
                    "amount": round(amt, 2),
                    "ref": ref,
                    "utr": s.settlement_utr,
                    "narration": narration(rng, s.bank_rail, sc.merchant, ref),
                }
            )
    rows.sort(key=lambda r: r["value_date"])
    return rows


# ------------------------------------------------------------- bank: MT940 ----

def bank_mt940(sc: Scenario, acct: str = "50200012345678", bank_bic: str = "HDFCINBB") -> str:
    rows = _payout_lines(sc)
    opening = 0.0
    lines = [":20:RECONAGENT" + datetime.now().strftime("%y%m%d"),
             f":25:{bank_bic}/{acct}",
             ":28C:00001/001",
             f":60F:C{datetime(2026, 8, 1).strftime('%y%m%d')}INR{opening:.2f}".replace(".", ",")]
    bal = opening
    for r in rows:
        d = r["value_date"].strftime("%y%m%d")
        entry = r["value_date"].strftime("%m%d")
        amt = f"{r['amount']:.2f}".replace(".", ",")
        lines.append(f":61:{d}{entry}C{amt}NTRFNONREF//{r['ref']}")
        lines.append(f":86:{r['narration']}")
        bal += r["amount"]
    lines.append(f":62F:C{datetime(2026, 8, 31).strftime('%y%m%d')}INR{bal:.2f}".replace(".", ","))
    return "\n".join(lines) + "\n"


# ------------------------------------------------------- bank: CAMT.053 XML ----

def bank_camt053(sc: Scenario, iban: str = "IN00HDFC0000012345678") -> str:
    rows = _payout_lines(sc)
    total = round(sum(r["amount"] for r in rows), 2)
    ents = []
    for r in rows:
        vd = r["value_date"].strftime("%Y-%m-%d")
        ents.append(f"""    <Ntry>
      <Amt Ccy="INR">{r['amount']:.2f}</Amt>
      <CdtDbtInd>CRDT</CdtDbtInd>
      <Sts>BOOK</Sts>
      <BookgDt><Dt>{vd}</Dt></BookgDt>
      <ValDt><Dt>{vd}</Dt></ValDt>
      <AcctSvcrRef>{escape(r['ref'])}</AcctSvcrRef>
      <BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>RCDT</Cd><SubFmlyCd>DMCT</SubFmlyCd></Fmly></Domn></BkTxCd>
      <NtryDtls><TxDtls>
        <Refs><EndToEndId>{escape(r['ref'])}</EndToEndId><TxId>{escape(r['utr'])}</TxId></Refs>
        <RmtInf><Ustrd>{escape(r['narration'])}</Ustrd></RmtInf>
      </TxDtls></NtryDtls>
    </Ntry>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
  <BkToCstmrStmt>
    <GrpHdr><MsgId>RECON-{datetime.now().strftime('%Y%m%d%H%M')}</MsgId><CreDtTm>{datetime.now().isoformat()}</CreDtTm></GrpHdr>
    <Stmt>
      <Id>STMT-2026-08</Id>
      <Acct><Id><IBAN>{iban}</IBAN></Id><Ccy>INR</Ccy></Acct>
      <Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp><Amt Ccy="INR">0.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2026-08-01</Dt></Dt></Bal>
      <Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy="INR">{total:.2f}</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2026-08-31</Dt></Dt></Bal>
{chr(10).join(ents)}
    </Stmt>
  </BkToCstmrStmt>
</Document>
"""


# --------------------------------------------------------- bank: HDFC CSV ----

def bank_hdfc_csv(sc: Scenario) -> str:
    rows = _payout_lines(sc)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.",
                "Deposit Amt.", "Closing Balance"])
    bal = 0.0
    for r in rows:
        bal += r["amount"]
        w.writerow([
            r["value_date"].strftime("%d/%m/%y"),
            r["narration"],
            r["ref"],
            r["value_date"].strftime("%d/%m/%y"),
            "",
            f"{r['amount']:.2f}",
            f"{bal:.2f}",
        ])
    return out.getvalue()


# --------------------------------------------------------- bank: ICICI CSV ----

def bank_icici_csv(sc: Scenario) -> str:
    rows = _payout_lines(sc)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["S No.", "Value Date", "Transaction Date", "Cheque Number",
                "Transaction Remarks", "Withdrawal Amount (INR )",
                "Deposit Amount (INR )", "Balance (INR )"])
    bal = 0.0
    for i, r in enumerate(rows, 1):
        bal += r["amount"]
        w.writerow([
            i,
            r["value_date"].strftime("%d/%m/%Y"),
            r["value_date"].strftime("%d/%m/%Y"),
            "",
            r["narration"],
            "0.00",
            f"{r['amount']:.2f}",
            f"{bal:.2f}",
        ])
    return out.getvalue()


EMITTERS = {
    "razorpay": ("pg_settlement_recon.csv", razorpay_recon),
    "ledger": ("ledger_zoho.csv", ledger_zoho),
    "mt940": ("bank_statement.mt940", bank_mt940),
    "camt": ("bank_statement.camt053.xml", bank_camt053),
    "hdfc": ("bank_statement_hdfc.csv", bank_hdfc_csv),
    "icici": ("bank_statement_icici.csv", bank_icici_csv),
}

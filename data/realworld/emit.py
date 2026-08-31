"""Render a Scenario into real-world, region-appropriate file formats.

  pg  : razorpay_recon (IN)  |  stripe_balance (US / EU)
  bank: hdfc / icici (IN)  |  us_csv (US)  |  camt / mt940 (EU or any)
  ledger: zoho-style CSV with presentment + settlement currency columns
"""

from __future__ import annotations

import csv
import io
import random
from datetime import datetime
from xml.sax.saxutils import escape

from .entities import narration
from .fx import subunit_factor
from .regions import REGIONS
from .scenario import Scenario

# ----------------------------------------------------------- locale helpers ----
# Bank/ledger CSV exports use a plain decimal (no thousands grouping — that is
# display-only). The decimal separator IS localized: '.' for IN/US, ',' for EU,
# and EU files are then ';'-delimited (German convention).

def _fmt_amount(x: float, region_code: str) -> str:
    dec = REGIONS[region_code].decimal_sep
    return f"{x:.2f}".replace(".", dec) if dec != "." else f"{x:.2f}"


def _csv_sep(region_code: str) -> str:
    return ";" if REGIONS[region_code].decimal_sep == "," else ","


def _fmt_date(d: datetime, region_code: str) -> str:
    return d.strftime(REGIONS[region_code].date_format)


def _minor(x: float, ccy: str) -> int:
    return int(round(x * subunit_factor(ccy)))


def _ts(dt: datetime | None) -> str:
    return "" if dt is None else str(int(dt.timestamp()))


# =========================================================== PG: Razorpay ====

_RECON_COLS = [
    "entity_id", "type", "debit", "credit", "amount", "currency", "fee", "tax",
    "on_hold", "settled", "created_at", "settled_at", "settlement_id", "posted_at",
    "credit_type", "description", "notes", "payment_id", "settlement_utr",
    "order_id", "order_receipt", "method", "card_network", "card_issuer",
    "card_type", "dispute_id",
]


def razorpay_recon(sc: Scenario) -> str:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=_RECON_COLS)
    w.writeheader()
    for p in sorted(sc.payments, key=lambda x: x.settled_at):
        refund = p.kind == "refund"
        amt = abs(p.gross)
        # `fee` folds in the FX markup + any unexplained deduction so that
        # amount - fee - tax == net always holds on the recon report.
        fee_total = 0.0 if refund else round(amt - p.net - p.charged_tax, 2)
        w.writerow({
            "entity_id": p.payment_id,
            "type": "refund" if refund else "payment",
            "debit": _minor(amt, sc.currency) if refund else 0,
            "credit": 0 if refund else _minor(p.net, sc.currency),
            "amount": _minor(amt, sc.currency),
            "currency": sc.currency,
            "fee": _minor(fee_total, sc.currency),
            "tax": _minor(p.charged_tax, sc.currency),
            "on_hold": str(p.on_hold), "settled": "True",
            "created_at": _ts(p.captured_at), "settled_at": _ts(p.settled_at),
            "settlement_id": p.settlement_id, "posted_at": "",
            "credit_type": "default",
            "description": ("Refund" if refund else "Payment")
            + (f" ({p.presentment_currency})" if p.cross_border else "")
            + f" via {p.method.upper()}",
            "notes": "", "payment_id": p.payment_id if refund else "",
            "settlement_utr": p.settlement_ref,
            "order_id": p.order_id, "order_receipt": p.order_receipt,
            "method": p.method, "card_network": p.card_network or "",
            "card_issuer": p.card_issuer or "", "card_type": p.card_type or "",
            "dispute_id": p.dispute_id or "",
        })
    return out.getvalue()


# =========================================================== PG: Stripe ======

_STRIPE_COLS = [
    "balance_transaction_id", "type", "source_id", "customer_facing_amount",
    "customer_facing_currency", "gross", "fee", "net", "currency", "created_utc",
    "available_on_utc", "description", "reporting_category", "automatic_payout_id",
    "payment_method_type", "card_brand", "order_id", "order_receipt", "fx_rate",
]


def stripe_balance(sc: Scenario) -> str:
    """Stripe payout-reconciliation (balance transactions) report."""
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=_STRIPE_COLS)
    w.writeheader()
    for p in sorted(sc.payments, key=lambda x: x.settled_at):
        refund = p.kind == "refund"
        gross = -abs(p.gross) if refund else p.gross
        net = round(p.net if not refund else gross, 2)
        fee = 0.0 if refund else round(gross - net, 2)   # gross - fee == net
        w.writerow({
            "balance_transaction_id": "txn_" + p.payment_id.split("_", 1)[-1],
            "type": "refund" if refund else "charge",
            "source_id": p.payment_id,
            "customer_facing_amount": f"{p.presentment_amount:.2f}",
            "customer_facing_currency": p.presentment_currency.lower(),
            "gross": f"{gross:.2f}", "fee": f"{fee:.2f}", "net": f"{net:.2f}",
            "currency": sc.currency.lower(),
            "created_utc": p.captured_at.strftime("%Y-%m-%d %H:%M:%S"),
            "available_on_utc": p.settled_at.strftime("%Y-%m-%d"),
            "description": ("Refund" if refund else "Payment")
            + (f" (fx {p.presentment_currency}->{sc.currency})" if p.cross_border else ""),
            "reporting_category": "refund" if refund else "charge",
            "automatic_payout_id": "po_" + p.settlement_id.split("_", 1)[-1],
            "payment_method_type": p.method, "card_brand": p.card_network or "",
            "order_id": p.order_id, "order_receipt": p.order_receipt,
            "fx_rate": f"{p.fx_rate:.6f}" if p.cross_border else "1.000000",
        })
    return out.getvalue()


# =========================================================== Ledger ==========

_LEDGER_COLS = [
    "Invoice Number", "Invoice Date", "Order ID", "Reference Number", "Customer Name",
    "Place of Supply", "Invoice Status", "Payment Mode", "Presentment Currency",
    "Presentment Amount", "Currency", "Total",
]


def ledger_zoho(sc: Scenario) -> str:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=_LEDGER_COLS, delimiter=_csv_sep(sc.region))
    w.writeheader()
    for le in sc.ledger:
        w.writerow({
            "Invoice Number": le.invoice_no,
            "Invoice Date": _fmt_date(le.invoice_date, sc.region),
            "Order ID": le.order_id, "Reference Number": le.order_receipt,
            "Customer Name": le.customer_name, "Place of Supply": le.city,
            "Invoice Status": "Paid", "Payment Mode": le.method.title(),
            "Presentment Currency": le.presentment_currency,
            "Presentment Amount": f"{le.presentment_amount:.2f}",
            "Currency": le.settlement_currency, "Total": f"{le.gross:.2f}",
        })
    return out.getvalue()


# =========================================================== bank rows =======

def _payout_lines(sc: Scenario) -> list[dict]:
    rng = random.Random(hash(sc.merchant) & 0xFFFF)
    rows: list[dict] = []
    for s in sc.settlements:
        if not s.bank_emitted:
            continue
        amounts = s.split_parts or [s.net_payout]
        for j, amt in enumerate(amounts):
            ref = s.settlement_ref if j == 0 else f"{s.settlement_ref}-{j+1}"
            rows.append({
                "value_date": s.bank_value_date, "amount": round(amt, 2), "ref": ref,
                "utr": s.settlement_ref,
                "narration": narration(rng, sc.region, s.bank_rail, sc.merchant, ref),
            })
    rows.sort(key=lambda r: r["value_date"])
    return rows


def bank_mt940(sc: Scenario, acct: str = "50200012345678") -> str:
    rows = _payout_lines(sc)
    lines = [":20:RECON" + datetime.now().strftime("%y%m%d"),
             f":25:{acct}", ":28C:00001/001",
             f":60F:C260801{sc.currency}0,00"]
    bal = 0.0
    for r in rows:
        d = r["value_date"].strftime("%y%m%d")
        amt = f"{abs(r['amount']):.2f}".replace(".", ",")
        lines.append(f":61:{d}{r['value_date'].strftime('%m%d')}C{amt}NTRFNONREF//{r['ref']}")
        lines.append(f":86:{r['narration']}")
        bal += r["amount"]
    lines.append(f":62F:C260831{sc.currency}{bal:.2f}".replace(".", ","))
    return "\n".join(lines) + "\n"


def bank_camt053(sc: Scenario, iban: str = "DE00000000000012345678") -> str:
    rows = _payout_lines(sc)
    total = round(sum(r["amount"] for r in rows), 2)
    ents = []
    for r in rows:
        vd = r["value_date"].strftime("%Y-%m-%d")
        ents.append(f"""    <Ntry>
      <Amt Ccy="{sc.currency}">{r['amount']:.2f}</Amt>
      <CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts>
      <BookgDt><Dt>{vd}</Dt></BookgDt><ValDt><Dt>{vd}</Dt></ValDt>
      <AcctSvcrRef>{escape(r['ref'])}</AcctSvcrRef>
      <BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>RCDT</Cd><SubFmlyCd>ESCT</SubFmlyCd></Fmly></Domn></BkTxCd>
      <NtryDtls><TxDtls>
        <Refs><EndToEndId>{escape(r['ref'])}</EndToEndId><TxId>{escape(r['utr'])}</TxId></Refs>
        <RmtInf><Ustrd>{escape(r['narration'])}</Ustrd></RmtInf>
      </TxDtls></NtryDtls>
    </Ntry>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
  <BkToCstmrStmt>
    <GrpHdr><MsgId>RECON-{datetime.now().strftime('%Y%m%d%H%M')}</MsgId><CreDtTm>{datetime.now().isoformat()}</CreDtTm></GrpHdr>
    <Stmt><Id>STMT-2026-08</Id>
      <Acct><Id><IBAN>{iban}</IBAN></Id><Ccy>{sc.currency}</Ccy></Acct>
      <Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp><Amt Ccy="{sc.currency}">0.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2026-08-01</Dt></Dt></Bal>
      <Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy="{sc.currency}">{total:.2f}</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2026-08-31</Dt></Dt></Bal>
{chr(10).join(ents)}
    </Stmt>
  </BkToCstmrStmt>
</Document>
"""


def bank_hdfc_csv(sc: Scenario) -> str:
    rows = _payout_lines(sc)
    out = io.StringIO()
    w = csv.writer(out, delimiter=_csv_sep(sc.region))
    w.writerow(["Date", "Narration", "Chq./Ref.No.", "Value Dt",
                "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"])
    bal = 0.0
    for r in rows:
        bal += r["amount"]
        w.writerow([_fmt_date(r["value_date"], sc.region), r["narration"], r["ref"],
                    _fmt_date(r["value_date"], sc.region), "",
                    _fmt_amount(r["amount"], sc.region), _fmt_amount(bal, sc.region)])
    return out.getvalue()


def bank_icici_csv(sc: Scenario) -> str:
    rows = _payout_lines(sc)
    out = io.StringIO()
    w = csv.writer(out, delimiter=_csv_sep(sc.region))
    w.writerow(["S No.", "Value Date", "Transaction Date", "Cheque Number",
                "Transaction Remarks", "Withdrawal Amount (INR )",
                "Deposit Amount (INR )", "Balance (INR )"])
    bal = 0.0
    for i, r in enumerate(rows, 1):
        bal += r["amount"]
        w.writerow([i, _fmt_date(r["value_date"], sc.region), _fmt_date(r["value_date"], sc.region),
                    "", r["narration"], "0.00",
                    _fmt_amount(r["amount"], sc.region), _fmt_amount(bal, sc.region)])
    return out.getvalue()


def bank_us_csv(sc: Scenario) -> str:
    """US bank statement CSV (Chase-style)."""
    rows = _payout_lines(sc)
    out = io.StringIO()
    w = csv.writer(out, delimiter=_csv_sep(sc.region))
    w.writerow(["Details", "Posting Date", "Description", "Amount", "Type", "Balance"])
    bal = 0.0
    for r in rows:
        bal += r["amount"]
        w.writerow(["CREDIT", _fmt_date(r["value_date"], sc.region), r["narration"],
                    _fmt_amount(r["amount"], sc.region), "ACH_CREDIT",
                    _fmt_amount(bal, sc.region)])
    return out.getvalue()


EMITTERS = {
    "razorpay": ("pg_settlement_recon.csv", razorpay_recon),
    "stripe": ("pg_stripe_balance.csv", stripe_balance),
    "ledger": ("ledger_export.csv", ledger_zoho),
    "mt940": ("bank_statement.mt940", bank_mt940),
    "camt": ("bank_statement.camt053.xml", bank_camt053),
    "hdfc": ("bank_statement_hdfc.csv", bank_hdfc_csv),
    "icici": ("bank_statement_icici.csv", bank_icici_csv),
    "us_csv": ("bank_statement_us.csv", bank_us_csv),
}

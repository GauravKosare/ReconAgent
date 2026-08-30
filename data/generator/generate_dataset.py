"""Synthetic reconciliation dataset generator.

Produces three mutually-consistent files plus a ground-truth answer key, so the
pipeline's accuracy can be measured objectively:

    pg.csv          payment-gateway settlement report
    bank.csv        bank statement (aggregated payouts, realistic narrations)
    ledger.csv      internal sales ledger
    ground_truth.json   injected defects + expected exception code per txn

Defects injected (configurable): FEE_MISMATCH, MISSING_PAYOUT, TIMING_GAP,
DUPLICATE, MISSING_IN_LEDGER, SHORT_SETTLEMENT.

Usage:
    python generate_dataset.py --txns 500 --out ../samples --seed 7
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

MDR = 2.0
GST = 18.0


def build(txns: int, seed: int) -> dict:
    fake = Faker("en_IN")
    Faker.seed(seed)
    random.seed(seed)

    start = datetime(2026, 8, 1)
    ledger, pg, bank, truth = [], [], [], []

    # decide defect assignments
    idxs = list(range(txns))
    random.shuffle(idxs)
    defects = {
        "FEE_MISMATCH": set(idxs[0 : max(1, txns // 25)]),
        "MISSING_PAYOUT": set(idxs[txns // 25 : txns // 25 + max(1, txns // 60)]),
        "TIMING_GAP": set(idxs[txns // 12 : txns // 12 + max(1, txns // 40)]),
        "SHORT_SETTLEMENT": set(idxs[txns // 8 : txns // 8 + max(1, txns // 70)]),
        "DUPLICATE": set(idxs[txns // 6 : txns // 6 + max(1, txns // 80)]),
        "MISSING_IN_LEDGER": set(idxs[txns // 5 : txns // 5 + max(1, txns // 80)]),
    }

    def code_for(i: int) -> str | None:
        for c, s in defects.items():
            if i in s:
                return c
        return None

    for i in range(txns):
        code = code_for(i)
        day = start + timedelta(days=random.randint(0, 27))
        gross = round(random.choice([199, 299, 499, 999, 1499, 2499, 4999]) * random.choice([1, 1, 1, 2]), 2)
        utr = f"UTR{random.randint(10**9, 10**10 - 1)}"
        order_id = f"ORD{100000 + i}"
        payment_id = f"pay_{fake.lexify('??????????')}"

        fee = round(gross * MDR / 100, 2)
        tax = round(fee * GST / 100, 2)
        net = round(gross - fee - tax, 2)
        settle_day = day + timedelta(days=2)

        # ---- ledger ----
        if code != "MISSING_IN_LEDGER":
            ledger.append(
                {
                    "order_id": order_id,
                    "utr": utr,
                    "amount": gross,
                    "date": day.strftime("%Y-%m-%d"),
                    "description": f"Sale {fake.company()}",
                    "status": "paid",
                }
            )

        # ---- pg settlement ----
        pg_fee = fee
        pg_net = net
        if code == "FEE_MISMATCH":
            pg_fee = round(fee + random.choice([1, 2, 3, 5]), 2)
            pg_net = round(gross - pg_fee - tax, 2)
        if code == "SHORT_SETTLEMENT":
            pg_net = round(net - random.choice([10, 25, 50, 100]), 2)

        pg_row = {
            "payment_id": payment_id,
            "order_id": order_id,
            "utr": utr,
            "amount": gross,
            "fee": pg_fee,
            "tax": tax,
            "net_amount": pg_net,
            "created_at": day.strftime("%Y-%m-%d"),
            "settled_at": settle_day.strftime("%Y-%m-%d"),
            "status": "settled" if code != "MISSING_PAYOUT" else "settled",
            "method": random.choice(["upi", "card", "netbanking"]),
        }
        pg.append(pg_row)
        if code == "DUPLICATE":
            pg.append(dict(pg_row))  # exact duplicate line

        # ---- bank credit ----
        emit_bank = code not in ("MISSING_PAYOUT",)
        bank_day = settle_day
        if code == "TIMING_GAP":
            bank_day = settle_day + timedelta(days=4)  # arrives late
        if emit_bank:
            bank.append(
                {
                    "value_date": bank_day.strftime("%Y-%m-%d"),
                    "credit": pg_net,
                    "utr": utr,
                    "narration": f"NEFT/RAZORPAY/{order_id}/{utr[-6:]}",
                    "ref_no": utr,
                }
            )

        truth.append(
            {
                "order_id": order_id,
                "utr": utr,
                "expected_code": code,  # None => should be a clean match
                "gross": gross,
                "expected_net": net,
                "pg_net": pg_net,
                "injected_impact_inr": round(net - pg_net, 2),  # money at risk (0 if none)
            }
        )

    random.shuffle(pg)
    random.shuffle(bank)
    random.shuffle(ledger)
    return {"ledger": ledger, "pg": pg, "bank": bank, "ground_truth": truth}


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--txns", type=int, default=500)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=str, default="../samples")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = build(args.txns, args.seed)

    _write_csv(out / "ledger.csv", data["ledger"])
    _write_csv(out / "pg.csv", data["pg"])
    _write_csv(out / "bank.csv", data["bank"])
    (out / "ground_truth.json").write_text(json.dumps(data["ground_truth"], indent=2))

    injected = sum(1 for t in data["ground_truth"] if t["expected_code"])
    print(f"wrote {args.txns} txns to {out} — {injected} injected defects")
    print("  ledger rows:", len(data["ledger"]))
    print("  pg rows    :", len(data["pg"]))
    print("  bank rows  :", len(data["bank"]))


if __name__ == "__main__":
    main()

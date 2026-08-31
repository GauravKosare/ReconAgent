"""CLI: run one reconciliation batch and print the summary.

    python scripts/run_batch.py --pg data/samples/pg.csv \
        --bank data/samples/bank.csv --ledger data/samples/ledger.csv [--no-persist]

Optionally score against a ground-truth key:

    python scripts/run_batch.py ... --truth data/samples/ground_truth.json

Add --realistic for real multi-format statements with aggregated bank payouts
(Razorpay recon CSV / MT940 / CAMT.053 / bank CSV / Zoho ledger — auto-detected):

    python scripts/run_batch.py --realistic \
        --pg  data/samples/realworld/pg_settlement_recon.csv \
        --bank data/samples/realworld/bank_statement_hdfc.csv \
        --ledger data/samples/realworld/ledger_zoho.csv --no-persist
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.pipeline.realistic import run_realistic_batch  # noqa: E402
from app.pipeline.runner import run_batch  # noqa: E402


def score(result: dict, truth_path: str) -> dict:
    truth = json.loads(Path(truth_path).read_text())
    expected = {t["order_id"]: t["expected_code"] for t in truth if t["expected_code"]}
    got_codes = result["summary"]["exceptions_by_code"]
    return {
        "injected_defects": len(expected),
        "exceptions_found": result["summary"]["exceptions"],
        "by_code_found": got_codes,
        "injected_by_code": _count(expected.values()),
    }


def _count(values) -> dict:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pg", required=True)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--truth")
    ap.add_argument("--no-persist", action="store_true")
    ap.add_argument("--realistic", action="store_true",
                    help="real multi-format statements with aggregated bank payouts")
    args = ap.parse_args()

    if args.realistic:
        result = run_realistic_batch(args.pg, args.bank, args.ledger, persist=not args.no_persist)
    else:
        result = run_batch(args.pg, args.bank, args.ledger, persist=not args.no_persist)
    print(json.dumps(result["summary"], indent=2))
    if args.truth:
        print("\n--- scoring vs ground truth ---")
        print(json.dumps(score(result, args.truth), indent=2))


if __name__ == "__main__":
    main()

"""CLI — write a realistic multi-format reconciliation dataset.

    python -m data.realworld.generate --profile d2c-brand --payments 500 \
        --bank hdfc --out data/samples/realworld --seed 7

Writes:
    pg_settlement_recon.csv     Razorpay recon report
    ledger_zoho.csv             internal ledger
    bank_statement*.{csv,mt940,xml}   one bank format (choose with --bank)
    ground_truth.json           answer key for scripts/evaluate.py
    dataset_manifest.json       stats + which files are which source
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

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from data.realworld.emit import EMITTERS
    from data.realworld.scenario import PROFILES, build_scenario
else:
    from .emit import EMITTERS
    from .scenario import PROFILES, build_scenario


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=list(PROFILES), default="d2c-brand")
    ap.add_argument("--payments", type=int, default=500)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--defect-rate", type=float, default=0.12)
    ap.add_argument("--bank", choices=["mt940", "camt", "hdfc", "icici"], default="hdfc")
    ap.add_argument("--out", type=str, default="data/samples/realworld")
    args = ap.parse_args()

    sc = build_scenario(args.profile, args.payments, args.seed, args.defect_rate)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    written = {}
    for key in ("razorpay", "ledger", args.bank):
        fname, fn = EMITTERS[key]
        (out / fname).write_text(fn(sc), encoding="utf-8")
        written[key] = fname

    (out / "ground_truth.json").write_text(json.dumps(sc.truth, indent=2), encoding="utf-8")
    manifest = {
        **sc.stats,
        "seed": args.seed,
        "files": {
            "pg": written["razorpay"],
            "ledger": written["ledger"],
            "bank": written[args.bank],
            "bank_format": args.bank,
        },
    }
    (out / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"wrote realistic dataset -> {out}")
    for k, v in sc.stats.items():
        print(f"  {k}: {v}")
    print("  files:", ", ".join(written.values()))


if __name__ == "__main__":
    main()

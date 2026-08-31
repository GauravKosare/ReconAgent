"""CLI — write a realistic, region-aware multi-format reconciliation dataset.

    python -m data.realworld.generate --region US --profile saas --payments 500 \
        --out data/samples/realworld --seed 7

Region picks the currency, tax treatment, MDR bands, rails and default PG/bank
formats. --pg / --bank override the defaults.
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
    from data.realworld.regions import REGIONS
    from data.realworld.scenario import PROFILES, build_scenario
else:
    from .emit import EMITTERS
    from .regions import REGIONS
    from .scenario import PROFILES, build_scenario


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", choices=list(REGIONS), default="IN")
    ap.add_argument("--profile", choices=list(PROFILES), default="d2c-brand")
    ap.add_argument("--payments", type=int, default=500)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--defect-rate", type=float, default=0.12)
    ap.add_argument("--pg", choices=["razorpay", "stripe"], default=None)
    ap.add_argument("--bank", choices=["mt940", "camt", "hdfc", "icici", "us_csv"], default=None)
    ap.add_argument("--out", type=str, default="data/samples/realworld")
    args = ap.parse_args()

    region = REGIONS[args.region]
    pg_key = args.pg or region.default_pg_format
    bank_key = args.bank or region.default_bank_format

    sc = build_scenario(args.profile, args.region, args.payments, args.seed, args.defect_rate)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    written = {}
    for key in (pg_key, "ledger", bank_key):
        fname, fn = EMITTERS[key]
        (out / fname).write_text(fn(sc), encoding="utf-8")
        written[key] = fname

    (out / "ground_truth.json").write_text(json.dumps(sc.truth, indent=2), encoding="utf-8")
    (out / "dataset_manifest.json").write_text(json.dumps({
        **sc.stats, "seed": args.seed,
        "files": {"pg": written[pg_key], "ledger": written["ledger"],
                  "bank": written[bank_key], "pg_format": pg_key, "bank_format": bank_key},
    }, indent=2), encoding="utf-8")

    print(f"wrote {args.region} / {args.profile} dataset -> {out}")
    for k, v in sc.stats.items():
        print(f"  {k}: {v}")
    print("  files:", ", ".join(written.values()))


if __name__ == "__main__":
    main()

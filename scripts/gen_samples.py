"""Regenerate the committed sample-dataset matrix under data/samples/realworld/.

Each entry exercises a region + profile + a specific PG/bank format so the
parsers and the reconciler are covered end to end. Run after changing the
generator or the formats:

    python scripts/gen_samples.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.realworld.emit import EMITTERS  # noqa: E402
from data.realworld.scenario import build_scenario  # noqa: E402

OUT = ROOT / "data" / "samples" / "realworld"

# (folder, region, profile, pg_format, bank_format, payments, seed)
# `strong` datasets must clear the score bar in tests; the rest only round-trip
# (marketplace TDS/reserve + IFR caps + FX is a documented hard case).
MATRIX = [
    # folder                region profile      pg        bank    pay seed strong
    ("IN-d2c-hdfc",          "IN", "d2c-brand",   "razorpay", "hdfc",   400, 7,  True),
    ("IN-saas-mt940",        "IN", "saas",        "razorpay", "mt940",  350, 11, True),
    ("IN-travel-icici",      "IN", "travel",      "razorpay", "icici",  350, 23, True),
    ("IN-marketplace-hdfc",  "IN", "marketplace", "razorpay", "hdfc",   400, 7,  False),
    ("US-d2c-chase",         "US", "d2c-brand",   "stripe",   "us_csv", 400, 7,  True),
    ("US-saas-camt",         "US", "saas",        "stripe",   "camt",   400, 11, True),
    ("US-travel-chase",      "US", "travel",      "stripe",   "us_csv", 300, 23, True),
    ("EU-d2c-camt",          "EU", "d2c-brand",   "stripe",   "camt",   400, 31, True),
    ("EU-saas-mt940",        "EU", "saas",        "stripe",   "mt940",  350, 23, True),
    ("EU-travel-camt",       "EU", "travel",      "stripe",   "camt",   350, 11, True),
    ("EU-marketplace-camt",  "EU", "marketplace", "stripe",   "camt",   400, 11, False),
]


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    index = []
    for folder, region, profile, pg_key, bank_key, payments, seed, strong in MATRIX:
        d = OUT / folder
        d.mkdir(parents=True)
        sc = build_scenario(profile, region, payments, seed)
        files = {}
        for key in (pg_key, "ledger", bank_key):
            fname, fn = EMITTERS[key]
            (d / fname).write_text(fn(sc), encoding="utf-8")
            files[key] = fname
        (d / "ground_truth.json").write_text(json.dumps(sc.truth, indent=2), encoding="utf-8")
        manifest = {
            **sc.stats, "seed": seed,
            "files": {"pg": files[pg_key], "ledger": files["ledger"],
                      "bank": files[bank_key], "pg_format": pg_key, "bank_format": bank_key},
        }
        (d / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        index.append({"folder": folder, "region": region, "profile": profile,
                      "pg_format": pg_key, "bank_format": bank_key, "strong": strong,
                      "payments": sc.stats["payments"], "currency": sc.stats["currency"],
                      "cross_border": sc.stats["cross_border_payments"],
                      "injected_defects": sc.stats["injected_defects"]})
        print(f"  {folder:22} {region} {profile:11} {pg_key:8} {bank_key:6} "
              f"{sc.stats['payments']:4}p  {sc.stats['injected_defects']:3} defects")

    (OUT / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    _write_readme(index)
    print(f"\nwrote {len(MATRIX)} datasets -> {OUT}")


def _write_readme(index: list[dict]) -> None:
    rows = "\n".join(
        f"| `{i['folder']}` | {i['region']} | {i['profile']} | {i['currency']} | "
        f"{i['pg_format']} + {i['bank_format']} | {i['payments']} | {i['cross_border']} | "
        f"{i['injected_defects']} |"
        for i in index
    )
    (OUT / "README.md").write_text(
        "# Sample datasets — `data/samples/realworld/`\n\n"
        "Committed reconciliation datasets covering every region, several merchant\n"
        "profiles, and every statement format. Regenerate with `python scripts/gen_samples.py`.\n\n"
        "Each folder has the three source files + `ground_truth.json` + `dataset_manifest.json`.\n\n"
        "| Folder | Region | Profile | Ccy | Formats | Payments | Cross-border | Injected defects |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        f"{rows}\n\n"
        "Run one:\n\n"
        "```bash\n"
        "python scripts/run_batch.py --realistic --region EU \\\n"
        "  --pg     data/samples/realworld/EU-d2c-camt/pg_stripe_balance.csv \\\n"
        "  --bank   data/samples/realworld/EU-d2c-camt/bank_statement.camt053.xml \\\n"
        "  --ledger data/samples/realworld/EU-d2c-camt/ledger_export.csv --no-persist\n"
        "```\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

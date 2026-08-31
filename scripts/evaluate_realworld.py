"""Evaluate the realistic (multi-format, region-aware, multi-currency) pipeline.

    python scripts/evaluate_realworld.py --region US --profile saas --payments 500 --seeds 1,2,3

Generates a realistic dataset per seed, runs run_realistic_batch, scores against
ground_truth.json, prints a scorecard. Deterministic-only unless an LLM key is set.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("RECONAGENT_AUDIT_SINK", "none")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.metrics import score_batch  # noqa: E402
from app.pipeline.realistic import run_realistic_batch  # noqa: E402

from data.realworld.emit import EMITTERS  # noqa: E402
from data.realworld.regions import REGIONS  # noqa: E402
from data.realworld.scenario import build_scenario  # noqa: E402

_DEDUCTIONS = {"marketplace": (1.0, 5.0), "travel": (0.0, 5.0)}


def one(region: str, profile: str, payments: int, seed: int,
        bank: str | None, pg: str | None, defect_rate: float) -> dict:
    reg = REGIONS[region]
    pg_key = pg or reg.default_pg_format
    bank_key = bank or reg.default_bank_format
    sc = build_scenario(profile, region, payments, seed, defect_rate)
    tmp = Path(tempfile.mkdtemp(prefix=f"rweval_{region}_{seed}_"))
    files = {}
    for key in (pg_key, "ledger", bank_key):
        fname, fn = EMITTERS[key]
        (tmp / fname).write_text(fn(sc), encoding="utf-8")
        files[key] = str(tmp / fname)
    tds, reserve = _DEDUCTIONS.get(profile, (0.0, 0.0))
    result = run_realistic_batch(
        files[pg_key], files[bank_key], files["ledger"],
        region=region, tds_percent=tds, reserve_percent=reserve,
    )
    card = score_batch(result, sc.truth)
    return {"seed": seed, "stats": sc.stats, "summary": result["summary"],
            "card": card.to_dict(), "_card": card}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", choices=list(REGIONS), default="IN")
    ap.add_argument("--profile", default="d2c-brand")
    ap.add_argument("--payments", type=int, default=500)
    ap.add_argument("--seeds", default="7")
    ap.add_argument("--pg", choices=["razorpay", "stripe"], default=None)
    ap.add_argument("--bank", choices=["mt940", "camt", "hdfc", "icici", "us_csv"], default=None)
    ap.add_argument("--defect-rate", type=float, default=0.12)
    args = ap.parse_args()

    runs = [one(args.region, args.profile, args.payments, s, args.bank, args.pg, args.defect_rate)
            for s in (int(x) for x in args.seeds.split(","))]

    st0 = runs[0]["summary"]
    print(f"\n# Realistic pipeline — {args.region} ({st0.get('currency')}) / {args.profile} "
          f"· {args.payments} payments · pg={list(st0['formats'].values())}\n")
    for r in runs:
        s = r["summary"]
        print(f"seed {r['seed']}: {s['settlement_batches']} batches "
              f"({s['batches_reconciled']} reconciled), {s['auto_matched_groups']} lines auto-matched, "
              f"{r['stats'].get('cross_border_payments', 0)} cross-border, "
              f"{s['exceptions']} exceptions, {s['pending_approval']} to review")
        print(r["_card"].markdown())
        print()

    def mean(path):
        vals = []
        for r in runs:
            v = r["card"]
            for k in path:
                v = v.get(k) if isinstance(v, dict) else None
            if isinstance(v, (int, float)):
                vals.append(float(v))
        return round(statistics.fmean(vals), 3) if vals else None

    agg = {
        "auto_match_rate": mean(["throughput", "auto_match_rate"]),
        "detection_recall": mean(["detection", "recall"]),
        "detection_precision": mean(["detection", "precision"]),
        "classification_accuracy": mean(["classification", "accuracy"]),
        "money_recovery_ratio": mean(["money", "recovery_ratio"]),
    }
    print("## aggregate:", json.dumps(agg))
    if any(not r["card"]["overall_pass"] for r in runs):
        sys.exit(1)


if __name__ == "__main__":
    main()

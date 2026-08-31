"""Evaluate the realistic (multi-format, aggregated-payout) pipeline.

    python scripts/evaluate_realworld.py --profile d2c-brand --payments 500 \
        --bank hdfc --seeds 1,2,3

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
from data.realworld.scenario import build_scenario  # noqa: E402

_DEDUCTIONS = {  # merchant contract terms the reconciler needs told about
    "marketplace": (1.0, 5.0),
    "travel": (0.0, 5.0),
}


def one(profile: str, payments: int, seed: int, bank: str, defect_rate: float) -> dict:
    sc = build_scenario(profile, payments, seed, defect_rate)
    tmp = Path(tempfile.mkdtemp(prefix=f"rweval_{seed}_"))
    files = {}
    for key in ("razorpay", "ledger", bank):
        fname, fn = EMITTERS[key]
        (tmp / fname).write_text(fn(sc), encoding="utf-8")
        files[key] = str(tmp / fname)
    tds, reserve = _DEDUCTIONS.get(profile, (0.0, 0.0))
    result = run_realistic_batch(
        files["razorpay"], files[bank], files["ledger"],
        tds_percent=tds, reserve_percent=reserve,
    )
    card = score_batch(result, sc.truth)
    return {"seed": seed, "stats": sc.stats, "summary": result["summary"], "card": card.to_dict(),
            "_card": card}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="d2c-brand")
    ap.add_argument("--payments", type=int, default=500)
    ap.add_argument("--seeds", default="7")
    ap.add_argument("--bank", default="hdfc", choices=["mt940", "camt", "hdfc", "icici"])
    ap.add_argument("--defect-rate", type=float, default=0.12)
    args = ap.parse_args()

    runs = [one(args.profile, args.payments, s, args.bank, args.defect_rate)
            for s in (int(x) for x in args.seeds.split(","))]

    print(f"\n# Realistic pipeline — {args.profile} · {args.payments} payments · bank={args.bank}\n")
    for r in runs:
        s = r["summary"]
        print(f"seed {r['seed']}: {r['stats']['settlement_batches']} batches "
              f"({s['batches_reconciled']} reconciled), {s['auto_matched_groups']} lines auto-matched, "
              f"{s['exceptions']} exceptions, {s['pending_approval']} to review, runtime {s['runtime_seconds']}s")
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

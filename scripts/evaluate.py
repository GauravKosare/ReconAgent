"""Metrics-vs-ground-truth evaluation harness.

Generates one or more seeded synthetic datasets, runs the full reconciliation
pipeline on each (no DB writes), scores every run against its ground-truth key,
and emits an aggregate report (JSON + Markdown) with mean / std across seeds.

    # quick single run
    python scripts/evaluate.py --txns 500 --seeds 7

    # variance across 5 seeds, write report files
    python scripts/evaluate.py --txns 500 --seeds 1,2,3,4,5 --out reports

Runs with no LLM key configured still work - classification accuracy is then
reported as n/a while detection recall / throughput / money metrics are real.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import sys
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault("RECONAGENT_AUDIT_SINK", "none")  # keep the harness hermetic

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.metrics import score_batch  # noqa: E402
from app.pipeline.runner import run_batch  # noqa: E402

_gen_spec = importlib.util.spec_from_file_location(
    "reconagent_gen", ROOT / "data" / "generator" / "generate_dataset.py"
)
_gen = importlib.util.module_from_spec(_gen_spec)
_gen_spec.loader.exec_module(_gen)  # type: ignore[union-attr]


def _write_csv(path: Path, rows: list[dict]) -> None:
    import csv

    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def run_one(txns: int, seed: int) -> dict:
    data = _gen.build(txns, seed)
    tmp = Path(tempfile.mkdtemp(prefix=f"reconeval_{seed}_"))
    _write_csv(tmp / "ledger.csv", data["ledger"])
    _write_csv(tmp / "pg.csv", data["pg"])
    _write_csv(tmp / "bank.csv", data["bank"])

    result = run_batch(
        str(tmp / "pg.csv"), str(tmp / "bank.csv"), str(tmp / "ledger.csv"), persist=False
    )
    card = score_batch(result, data["ground_truth"])
    return card.to_dict() | {"_card": card, "seed": seed}


def aggregate(runs: list[dict]) -> dict:
    def series(path: list[str]) -> list[float]:
        out = []
        for r in runs:
            v = r
            for k in path:
                v = v.get(k) if isinstance(v, dict) else None
            if isinstance(v, (int, float)):
                out.append(float(v))
        return out

    keys = {
        "auto_match_rate": ["throughput", "auto_match_rate"],
        "runtime_seconds": ["throughput", "runtime_seconds"],
        "human_queue_fraction": ["throughput", "human_queue_fraction"],
        "detection_precision": ["detection", "precision"],
        "detection_recall": ["detection", "recall"],
        "classification_accuracy": ["classification", "accuracy"],
        "money_recovery_ratio": ["money", "recovery_ratio"],
    }
    agg = {}
    for name, path in keys.items():
        vals = series(path)
        if not vals:
            agg[name] = None
            continue
        agg[name] = {
            "mean": round(statistics.fmean(vals), 4),
            "std": round(statistics.pstdev(vals), 4) if len(vals) > 1 else 0.0,
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
            "n": len(vals),
        }
    agg["overall_pass_rate"] = round(
        sum(1 for r in runs if r.get("overall_pass")) / len(runs), 3
    )
    return agg


def to_markdown(txns: int, runs: list[dict], agg: dict) -> str:
    lines = [
        "# ReconAgent - Metrics vs Ground Truth",
        "",
        f"_Generated {datetime.utcnow().isoformat()}Z - {len(runs)} seed(s) - "
        f"{txns} transactions/run - LLM used: {runs[0]['classification']['llm_used']}_",
        "",
        ""
        if runs[0]["classification"]["llm_used"]
        else "> No LLM key configured: every unresolved cluster is `UNEXPLAINED`, so "
        "classification accuracy and money-recovery are **n/a**. Detection recall, "
        "auto-match rate, queue size and runtime are real. Set a `GEMINI_API_KEY` "
        "(or any provider) and re-run for the full scorecard.",
        "## Aggregate (mean +/- std across seeds)",
        "",
        "| Metric | Mean | Std | Min | Max | Target |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    trg = {
        "auto_match_rate": "&ge; 0.85",
        "detection_recall": "&ge; 0.85",
        "classification_accuracy": "&ge; 0.90",
        "human_queue_fraction": "&le; 0.15",
        "runtime_seconds": "&le; 300",
        "money_recovery_ratio": "0.95-1.05",
        "detection_precision": "-",
    }
    for name, target in trg.items():
        a = agg.get(name)
        if not a:
            lines.append(f"| {name} | n/a | | | | {target} |")
        else:
            lines.append(
                f"| {name} | {a['mean']} | {a['std']} | {a['min']} | {a['max']} | {target} |"
            )
    lines += ["", f"**Overall pass rate across seeds:** {agg['overall_pass_rate']:.0%}", ""]
    lines += ["## Per-seed detail", ""]
    for r in runs:
        lines += [f"### Seed {r['seed']}  (overall pass: {r['overall_pass']})", "", r["_card"].markdown(), ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--txns", type=int, default=500)
    ap.add_argument("--seeds", type=str, default="7", help="comma-separated seeds")
    ap.add_argument("--out", type=str, help="directory to write metrics_<ts>.{json,md}")
    args = ap.parse_args()

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    runs = [run_one(args.txns, s) for s in seeds]
    agg = aggregate(runs)
    md = to_markdown(args.txns, runs, agg)
    print(md)

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        payload = {
            "generated_at": ts,
            "txns_per_run": args.txns,
            "seeds": seeds,
            "aggregate": agg,
            "runs": [{k: v for k, v in r.items() if k != "_card"} for r in runs],
        }
        (out / f"metrics_{ts}.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        (out / f"metrics_{ts}.md").write_text(md, encoding="utf-8")
        print(f"\nwrote {out / f'metrics_{ts}.json'} and .md")

    if agg["overall_pass_rate"] < 1.0:
        sys.exit(1)


if __name__ == "__main__":
    main()

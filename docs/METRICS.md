# ReconAgent — Metrics vs Ground Truth

## Why a harness

The Buildathon rubric for Track 04 asks for **measured accuracy**, not a demo.
The synthetic data generator injects a known set of defects and writes an answer
key (`ground_truth.json`); the harness replays the pipeline and grades it against
that key, so every claim in the pitch is a number you can reproduce.

## Running it

```bash
# single run
python scripts/evaluate.py --txns 500 --seeds 7

# variance across seeds, write reports/metrics_<ts>.{json,md}
python scripts/evaluate.py --txns 500 --seeds 1,2,3,4,5 --out reports
```

Exit code is `0` only if every seed meets every applicable target.

`scripts/run_batch.py --truth data/samples/ground_truth.json` gives a quick
single-batch score without the multi-seed machinery.

## What it measures

| Metric | Definition | Target |
| --- | --- | --- |
| **Auto-match rate** | exact 3-way `match_groups` ÷ transactions | ≥ 0.85 |
| **Detection recall** | injected defects that produced *any* exception ÷ all injected defects | ≥ 0.85 |
| **Detection precision** | true defects flagged ÷ all flagged (incl. false positives on clean rows) | reported |
| **Classification accuracy** | detected defects given the *correct* taxonomy code ÷ detected | ≥ 0.90 (LLM runs only) |
| **Per-code P / R / F1** | one row per taxonomy code, with a confusion matrix (expected → predicted) | reported |
| **Human queue fraction** | `pending_approval` ÷ transactions | ≤ 0.15 |
| **Runtime** | wall-clock for the batch | ≤ 300 s |
| **Money recovery ratio** | Σ\|`amount_impact`\| surfaced ÷ Σ injected `injected_impact_inr` | 0.95–1.05 (LLM runs only) |

## How mapping works

Exceptions are keyed by `cluster_id`; the scorer maps each back to an
`order_id` via the cluster anchor's `external_id` (an `ORD…` id) or, failing
that, its `utr` looked up in the ground-truth key. Unmapped exceptions count as
false positives.

## Running without an LLM

With no provider key, every unresolved cluster is `UNEXPLAINED`:

- **Real:** auto-match rate, detection recall/precision, queue fraction, runtime.
- **n/a:** classification accuracy, per-code F1, money recovery (these need the
  agent to assign codes and rupee impact).

This is intentional — it lets CI and offline dev verify the deterministic core
without spending API quota. Set `GEMINI_API_KEY` (or any provider in the chain)
and re-run for the complete scorecard.

## Interpreting a low score

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| Auto-match rate low | key/tolerance too strict, or date windows off | `matching/exact.py` |
| Detection recall low | candidate generator not surfacing the cluster | `matching/candidates.py` weights |
| Classification accuracy low | prompt / taxonomy ambiguity, weak fallback model | `agent/adjudicator.py`, provider chain |
| Many false positives | candidate generator too eager, or routing not conservative | `candidates.py`, `pipeline/routing.py` |
| Money ratio ≠ 1 | agent mis-sizing impact, or guardrail miscalibrated | `agent/adjudicator.py` guardrail |

## Note on variance

The current generator fixes defect *counts* per size, so deterministic metrics
are near-identical across seeds — variance in a full run comes from LLM
non-determinism. To stress the matcher, vary `--txns` and edit the defect ratios
in `data/generator/generate_dataset.py`.

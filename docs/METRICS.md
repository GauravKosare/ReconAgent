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

## Current status (honest)

Latest LLM-backed run (`reports/metrics_*.md`, 100 txns):

| Metric | Value | Target | State |
| --- | --- | --- | --- |
| Auto-match rate | ~92% | &ge; 85% | PASS |
| Detection recall | ~90% | &ge; 85% | PASS (defects are surfaced) |
| Detection precision | 100% | - | PASS (no false alarms on clean rows) |
| Human queue | ~3% | &le; 15% | PASS |
| Runtime (100 txns) | ~90s | &le; 300s | PASS |
| **Classification accuracy** | **~40%** | &ge; 90% | **NEEDS TUNING** |
| Money recovery ratio | ~2.4 | 0.95-1.05 | follows classification |

The deterministic core and the detection layer are solid. **Code
classification** — putting the right taxonomy label on a surfaced exception — is
not yet good: `TIMING_GAP`, `MISSING_PAYOUT`, `SHORT_SETTLEMENT` and
`MISSING_IN_LEDGER` are mostly mislabelled as `FEE_MISMATCH` or missed. Known
causes, in priority order:

1. The Gemini free quota is easily exhausted by repeated eval runs, so the work
   falls to Groq Qwen-3-27B, which follows the taxonomy checklist loosely.
   Fixes: run evals sparingly; make Gemini genuinely primary for the demo batch;
   add a stronger free model.
2. The tool report doesn't yet make the timing signal unambiguous (needs an
   explicit `expected_bank_credit: present|absent|late` field).
3. The prompt needs few-shot examples per code, not just a checklist.
4. `SHORT_SETTLEMENT` vs `FEE_MISMATCH` overlap — tighten the generator and the
   code definitions.

This is the next focused work item, tracked separately from the harness itself.

## Note on variance

The current generator fixes defect *counts* per size, so deterministic metrics
are near-identical across seeds — variance in a full run comes from LLM
non-determinism. To stress the matcher, vary `--txns` and edit the defect ratios
in `data/generator/generate_dataset.py`.

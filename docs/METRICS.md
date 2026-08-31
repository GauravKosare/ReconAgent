# ReconAgent — Metrics vs Ground Truth

## Why a harness

The Buildathon rubric for Track 04 asks for **measured accuracy**, not a demo.
The synthetic data generator injects a known set of defects and writes an answer
key (`ground_truth.json`); the harness replays the pipeline and grades it against
that key, so every claim in the pitch is a number you can reproduce.

## Running it

```bash
# single run, scored, no report files
python scripts/run_batch.py --pg data/samples/pg.csv --bank data/samples/bank.csv \
  --ledger data/samples/ledger.csv --truth data/samples/ground_truth.json

# multi-seed harness -> reports/metrics_<ts>.{json,md}
python scripts/evaluate.py --txns 500 --seeds 1,2,3 --out reports

# deterministic-only (no API calls) — force the no-LLM path
GEMINI_API_KEY= GROQ_API_KEY= OPENROUTER_API_KEY= python scripts/evaluate.py --txns 500 --seeds 1,2,3
```

Exit code is `0` only if every seed meets every applicable target.

## What it measures

| Metric | Definition | Target |
| --- | --- | --- |
| **Auto-match rate** | exact 3-way `match_groups` / transactions | &ge; 0.85 |
| **Detection recall** | injected defects that produced *any* exception / all injected | &ge; 0.85 |
| **Detection precision** | true defects flagged / all flagged (incl. false positives) | reported |
| **Classification accuracy** | detected defects given the *correct* taxonomy code / detected | &ge; 0.90 |
| **Per-code P / R / F1** | one row per taxonomy code + confusion matrix (expected -> predicted) | reported |
| **Human queue fraction** | `pending_approval` / transactions | &le; 0.15 |
| **Runtime** | wall-clock for the batch | &le; 300 s |
| **Money recovery ratio** | sum \|`amount_impact`\| on deduction codes / sum injected `injected_impact_inr` | 0.95-1.05 |

## Latest results

**LLM-backed** (`reports/latest_scorecard.md`, 200 txns, Gemini->Groq chain):

| Metric | Value | Target | |
| --- | --- | --- | --- |
| Auto-match rate | 90.5% | &ge; 85% | PASS |
| Detection recall | 100% | &ge; 85% | PASS |
| Detection precision | 100% | - | PASS |
| Classification accuracy | 100% | &ge; 90% | PASS |
| Per-code F1 | 100% on all 6 codes | - | PASS |
| Human queue | 7.5% | &le; 15% | PASS |
| Runtime | 119 s | &le; 300 s | PASS |
| Money recovery ratio | 1.00 | 0.95-1.05 | PASS |

**Deterministic-only** (`reports/deterministic_only_scorecard.md`, 500 txns x 3 seeds,
no API calls): auto-match 90%, detection recall 100%, per-code F1 100% on all
seven outcomes, queue ~10%, < 1 s.

### Why classification is accurate

The label is decided by `matching/compute_signals()` — deterministic rules over
UTR-linked, like-for-like amount comparisons — not by the LLM. The LLM only
*confirms* the deterministic suggestion (which unlocks auto-resolution) or
*disagrees* (which caps confidence and routes to a human). It can never silently
change a money decision, so accuracy tracks the rules, and the rules are exact on
the synthetic data.

## How mapping works

Exceptions carry the cluster anchor's `external_id` and `utr`. The scorer maps
each exception back to an `order_id` via the `ORD…` id or the `utr` in the
ground-truth key. Unmapped exceptions count as false positives.

## Interpreting a regression

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| Auto-match rate low | key/tolerance too strict, or date windows off | `matching/exact.py` |
| Detection recall low | true counterpart not in the candidate list | `matching/candidates.py` (MAX_CANDIDATES, UTR boost) |
| Classification wrong | a `compute_signals` rule mis-fires | `matching/signals.py` + `tests/test_signals.py` |
| Auto-resolve too low | LLM not confirming (rate-limited / weak model) | provider chain in `.env` |
| Money ratio off | `suggested_amount_impact` wrong for a code | `matching/signals.py` |

## Note on variance

The generator fixes defect *counts* per size, so deterministic metrics are
near-identical across seeds; run-to-run variance comes from LLM non-determinism
and free-tier rate limits (which only affect the auto-resolve rate, never the
classification). Vary `--txns` and the defect ratios in
`data/generator/generate_dataset.py` to stress the matcher.

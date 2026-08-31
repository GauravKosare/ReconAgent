# ReconAgent - Metrics vs Ground Truth

_Generated 2026-08-31T05:36:44.062738Z - 1 seed(s) - 200 transactions/run - LLM used: True_


## Aggregate (mean +/- std across seeds)

| Metric | Mean | Std | Min | Max | Target |
| --- | --- | --- | --- | --- | --- |
| auto_match_rate | 0.905 | 0.0 | 0.905 | 0.905 | &ge; 0.85 |
| detection_recall | 1.0 | 0.0 | 1.0 | 1.0 | &ge; 0.85 |
| classification_accuracy | 1.0 | 0.0 | 1.0 | 1.0 | &ge; 0.90 |
| human_queue_fraction | 0.075 | 0.0 | 0.075 | 0.075 | &le; 0.15 |
| runtime_seconds | 119.0 | 0.0 | 119.0 | 119.0 | &le; 300 |
| money_recovery_ratio | 1.0 | 0.0 | 1.0 | 1.0 | 0.95-1.05 |
| detection_precision | 1.0 | 0.0 | 1.0 | 1.0 | - |

**Overall pass rate across seeds:** 100%

## Per-seed detail

### Seed 3  (overall pass: True)

| Metric | Value | Target | Pass |
| --- | --- | --- | --- |
| Auto-match rate | 90.5% | &ge; 85% | PASS |
| Detection recall | 100.0% | &ge; 85% | PASS |
| Detection precision | 100.0% | - | - |
| Classification accuracy | 100.0% | &ge; 90% | PASS |
| Human queue | 7.5% | &le; 15% | PASS |
| Runtime | 119.0s | &le; 300s | PASS |
| Money recovery ratio | 1.00 | 0.95-1.05 | PASS |

**Per-code F1:**

| Code | P | R | F1 | TP/FP/FN |
| --- | --- | --- | --- | --- |
| DUPLICATE | 100.0% | 100.0% | 100.0% | 2/0/0 |
| FEE_MISMATCH | 100.0% | 100.0% | 100.0% | 8/0/0 |
| MISSING_IN_LEDGER | 100.0% | 100.0% | 100.0% | 2/0/0 |
| MISSING_PAYOUT | 100.0% | 100.0% | 100.0% | 3/0/0 |
| SHORT_SETTLEMENT | 100.0% | 100.0% | 100.0% | 2/0/0 |
| TIMING_GAP | 100.0% | 100.0% | 100.0% | 5/0/0 |

# ReconAgent - Metrics vs Ground Truth

_Generated 2026-08-31T06:05:48.447424Z - 1 seed(s) - 500 transactions/run - LLM used: True_


## Aggregate (mean +/- std across seeds)

| Metric | Mean | Std | Min | Max | Target |
| --- | --- | --- | --- | --- | --- |
| auto_match_rate | 0.899 | 0.0 | 0.899 | 0.899 | &ge; 0.85 |
| detection_recall | 1.0 | 0.0 | 1.0 | 1.0 | &ge; 0.85 |
| classification_accuracy | 1.0 | 0.0 | 1.0 | 1.0 | &ge; 0.90 |
| human_queue_fraction | 0.117 | 0.0 | 0.117 | 0.117 | &le; 0.15 |
| runtime_seconds | 13.5 | 0.0 | 13.5 | 13.5 | &le; 300 |
| money_recovery_ratio | 1.0 | 0.0 | 1.0 | 1.0 | 0.95-1.05 |
| detection_precision | 1.0 | 0.0 | 1.0 | 1.0 | - |

**Overall pass rate across seeds:** 100%

## Per-seed detail

### Seed 33  (overall pass: True)

| Metric | Value | Target | Pass |
| --- | --- | --- | --- |
| Auto-match rate | 89.9% | &ge; 85% | PASS |
| Detection recall | 100.0% | &ge; 85% | PASS |
| Detection precision | 100.0% | - | - |
| Classification accuracy | 100.0% | &ge; 90% | PASS |
| Human queue | 11.7% | &le; 15% | PASS |
| Runtime | 13.5s | &le; 300s | PASS |
| Money recovery ratio | 1.00 | 0.95-1.05 | PASS |

**Per-code F1:**

| Code | P | R | F1 | TP/FP/FN |
| --- | --- | --- | --- | --- |
| DUPLICATE | 100.0% | 100.0% | 100.0% | 6/0/0 |
| FEE_MISMATCH | 100.0% | 100.0% | 100.0% | 20/0/0 |
| MISSING_IN_LEDGER | 100.0% | 100.0% | 100.0% | 6/0/0 |
| MISSING_PAYOUT | 100.0% | 100.0% | 100.0% | 8/0/0 |
| SHORT_SETTLEMENT | 100.0% | 100.0% | 100.0% | 7/0/0 |
| TIMING_GAP | 100.0% | 100.0% | 100.0% | 12/0/0 |

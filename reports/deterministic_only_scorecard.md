# ReconAgent - Metrics vs Ground Truth

_Generated 2026-08-31T05:30:37.113274Z - 3 seed(s) - 500 transactions/run - LLM used: False_

> No LLM key configured: every unresolved cluster is `UNEXPLAINED`, so classification accuracy and money-recovery are **n/a**. Detection recall, auto-match rate, queue size and runtime are real. Set a `GEMINI_API_KEY` (or any provider) and re-run for the full scorecard.
## Aggregate (mean +/- std across seeds)

| Metric | Mean | Std | Min | Max | Target |
| --- | --- | --- | --- | --- | --- |
| auto_match_rate | 0.899 | 0.0 | 0.899 | 0.899 | &ge; 0.85 |
| detection_recall | 1.0 | 0.0 | 1.0 | 1.0 | &ge; 0.85 |
| classification_accuracy | n/a | | | | &ge; 0.90 |
| human_queue_fraction | 0.119 | 0.0 | 0.119 | 0.119 | &le; 0.15 |
| runtime_seconds | 0.2 | 0.0 | 0.2 | 0.2 | &le; 300 |
| money_recovery_ratio | 1.0 | 0.0 | 1.0 | 1.0 | 0.95-1.05 |
| detection_precision | 1.0 | 0.0 | 1.0 | 1.0 | - |

**Overall pass rate across seeds:** 100%

## Per-seed detail

### Seed 1  (overall pass: True)

| Metric | Value | Target | Pass |
| --- | --- | --- | --- |
| Auto-match rate | 89.9% | &ge; 85% | PASS |
| Detection recall | 100.0% | &ge; 85% | PASS |
| Detection precision | 100.0% | - | - |
| Classification accuracy | n/a | &ge; 90% | - |
| Human queue | 11.9% | &le; 15% | PASS |
| Runtime | 0.2s | &le; 300s | PASS |
| Money recovery ratio | 1.00 | 0.95-1.05 | - |

**Per-code F1:**

| Code | P | R | F1 | TP/FP/FN |
| --- | --- | --- | --- | --- |
| DUPLICATE | 100.0% | 100.0% | 100.0% | 6/0/0 |
| FEE_MISMATCH | 100.0% | 100.0% | 100.0% | 20/0/0 |
| MISSING_IN_LEDGER | 100.0% | 100.0% | 100.0% | 6/0/0 |
| MISSING_PAYOUT | 100.0% | 100.0% | 100.0% | 8/0/0 |
| SHORT_SETTLEMENT | 100.0% | 100.0% | 100.0% | 7/0/0 |
| TIMING_GAP | 100.0% | 100.0% | 100.0% | 12/0/0 |

### Seed 2  (overall pass: True)

| Metric | Value | Target | Pass |
| --- | --- | --- | --- |
| Auto-match rate | 89.9% | &ge; 85% | PASS |
| Detection recall | 100.0% | &ge; 85% | PASS |
| Detection precision | 100.0% | - | - |
| Classification accuracy | n/a | &ge; 90% | - |
| Human queue | 11.9% | &le; 15% | PASS |
| Runtime | 0.2s | &le; 300s | PASS |
| Money recovery ratio | 1.00 | 0.95-1.05 | - |

**Per-code F1:**

| Code | P | R | F1 | TP/FP/FN |
| --- | --- | --- | --- | --- |
| DUPLICATE | 100.0% | 100.0% | 100.0% | 6/0/0 |
| FEE_MISMATCH | 100.0% | 100.0% | 100.0% | 20/0/0 |
| MISSING_IN_LEDGER | 100.0% | 100.0% | 100.0% | 6/0/0 |
| MISSING_PAYOUT | 100.0% | 100.0% | 100.0% | 8/0/0 |
| SHORT_SETTLEMENT | 100.0% | 100.0% | 100.0% | 7/0/0 |
| TIMING_GAP | 100.0% | 100.0% | 100.0% | 12/0/0 |

### Seed 3  (overall pass: True)

| Metric | Value | Target | Pass |
| --- | --- | --- | --- |
| Auto-match rate | 89.9% | &ge; 85% | PASS |
| Detection recall | 100.0% | &ge; 85% | PASS |
| Detection precision | 100.0% | - | - |
| Classification accuracy | n/a | &ge; 90% | - |
| Human queue | 11.9% | &le; 15% | PASS |
| Runtime | 0.2s | &le; 300s | PASS |
| Money recovery ratio | 1.00 | 0.95-1.05 | - |

**Per-code F1:**

| Code | P | R | F1 | TP/FP/FN |
| --- | --- | --- | --- | --- |
| DUPLICATE | 100.0% | 100.0% | 100.0% | 6/0/0 |
| FEE_MISMATCH | 100.0% | 100.0% | 100.0% | 20/0/0 |
| MISSING_IN_LEDGER | 100.0% | 100.0% | 100.0% | 6/0/0 |
| MISSING_PAYOUT | 100.0% | 100.0% | 100.0% | 8/0/0 |
| SHORT_SETTLEMENT | 100.0% | 100.0% | 100.0% | 7/0/0 |
| TIMING_GAP | 100.0% | 100.0% | 100.0% | 12/0/0 |

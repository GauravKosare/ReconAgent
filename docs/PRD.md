# ReconAgent — Product Requirements Document

## 1. Context

**Event:** Razorpay AI Buildathon — **Track 04: AI Finance Controller**
("build agents that close finance-ops loops across 50+ record batches;
success = throughput, measured accuracy, documented exception handling").

**Team:** solo student build, ~2 weeks, ₹0 budget.

## 2. Problem statement

Businesses using a payment gateway must reconcile three records every settlement
cycle — internal ledger, PG settlement report, bank statement. MDR fees, GST,
refunds, chargebacks, `T+2` timing and split/bulk payouts create a long tail of
mismatches that junior finance staff resolve manually in spreadsheets. This is
slow, error-prone, and silently leaks money (over-charged fees, missing payouts,
double refunds).

## 3. Goal

Automatically reconcile a batch of transactions across the three sources,
resolve the unambiguous majority with zero human effort, and hand a human a
small, prioritised, fully-explained queue of the rest — with a complete audit
trail and a measurable accuracy number.

## 4. Users

| User | Need |
| --- | --- |
| Finance analyst | Stop hand-matching thousands of rows; trust the auto-matches; review only exceptions |
| Finance manager | Evidence for every "resolved" mark; know how much money is at risk |
| Auditor | Reconstruct any decision months later |

## 5. Scope

### In scope (MVP)

- Ingest 3 CSV/XLSX files with flexible column mapping.
- Deterministic three-way exact match.
- Candidate generation (amount + date + fuzzy string; semantic optional).
- Agent adjudication into a 10-code exception taxonomy.
- Bounded routing policy (confidence + rupee ceiling + code allowlist).
- Human approval queue (approve / edit / reject).
- Append-only audit log + `agent_runs` traceability.
- Metrics report vs a synthetic ground-truth key.
- Provider-agnostic free-tier LLM with automatic failover; degrades to
  "everything to human" with no LLM.

### Out of scope (MVP) / future

- Live Razorpay API ingestion (use exported report formats instead).
- Learning from reviewer rejections (feedback loop).
- FX and multi-entity consolidation beyond a single currency delta code.
- Auth / multi-tenant / RBAC (single-user demo).
- Writing corrections back to an external accounting system.

## 6. Functional requirements

| # | Requirement |
| --- | --- |
| F1 | Accept three uploaded files; reject if a required logical column cannot be mapped |
| F2 | Persist raw rows verbatim before any transformation |
| F3 | Produce `match_groups` with method = exact for all clean three-way ties |
| F4 | For every leftover, produce ≤3 ranked candidates |
| F5 | For every unresolved cluster, produce a `Verdict` validated against the schema |
| F6 | Re-derive `amount_impact` in code and flag disagreement |
| F7 | Route each verdict per the policy; never auto-resolve an `ALWAYS_HUMAN` code |
| F8 | Record an `audit_log` entry for ingest, match, adjudication, route, approval |
| F9 | Expose approval queue + audit + metrics via API and UI |
| F10 | Run end-to-end with no LLM key configured (all clusters → approval queue) |

## 7. Non-functional requirements

| # | Requirement | Target |
| --- | --- | --- |
| N1 | Cost | ₹0 / month (all free tiers) |
| N2 | LLM calls per 500-txn batch | ≤ 60 |
| N3 | Batch runtime (500 txns) | ≤ 5 min |
| N4 | No vendor lock-in | provider swap = config change only |
| N5 | Reproducibility | seeded synthetic data + deterministic core |
| N6 | Auditability | every decision reconstructable from `audit_log` + `agent_runs` |

## 8. Success metrics (what the demo must show)

| Metric | Definition | Target on synthetic 500-txn batch |
| --- | --- | --- |
| Auto-match rate | exact `match_groups` / transactions | ≥ 85% |
| Exception classification precision | correct code / codes assigned | ≥ 0.90 |
| Exception classification recall | injected defects caught | ≥ 0.85 |
| `UNEXPLAINED` correctness | genuinely ambiguous items flagged, not mislabelled | qualitative |
| ₹ at risk surfaced | sum of \|amount_impact\| on exceptions | matches injected total ± 5% |
| Human queue size | pending_approval count | ≤ 15% of transactions |
| Runtime | wall clock | ≤ 5 min |

## 9. Build plan

| Day | Deliverable |
| --- | --- |
| 1–2 | Repo, schemas, Atlas cluster, synthetic data generator, normalizer |
| 3–4 | Exact matcher + candidate generator; auto-match rate high on clean data |
| 5–7 | ModelClient + adjudicator + tools + taxonomy + routing policy + guardrails |
| 8–9 | Next.js dashboard, approval queue, audit viewer |
| 10–11 | Metrics harness vs ground truth; threshold tuning; semantic narration match |
| 12 | Architecture doc polish + 5-min pitch video |
| +2 | Buffer |

## 10. Risks

| Risk | Mitigation |
| --- | --- |
| Free-tier rate limits during demo | failover chain + response cache + deterministic core does 90% |
| Small open models misclassify hard clusters | those are low-confidence → already routed to human |
| Synthetic data feels unrealistic | model real narration strings, T+2 timing, split payouts, GST |
| Scope creep | taxonomy frozen at 10 codes; cut list in §5 |

## 11. Deliverables for submission

1. Public repository (this repo).
2. 5-minute pitch video: live batch run → approve one exception → metrics screen.
3. Architecture documentation (`docs/ARCHITECTURE.md`).

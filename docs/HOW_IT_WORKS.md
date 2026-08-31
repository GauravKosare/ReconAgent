# ReconAgent — How the whole thing works

A single walk-through of the system, from "user has three files" to "human clicks
approve". For the diagrams and the data model see
[`ARCHITECTURE.md`](ARCHITECTURE.md); for the AI specifics see
[`AI_INTEGRATION.md`](AI_INTEGRATION.md).

---

## The one-sentence version

ReconAgent takes three exports that should agree — the payment-gateway
settlement report, the bank statement, the internal sales ledger — matches every
transaction across all three, and for the ones that don't line up it says
*exactly what's wrong*, *how much money it's worth*, and *whether a human needs
to look*, with a full audit trail.

---

## The players

| File | Who produces it | What it claims |
| --- | --- | --- |
| **Ledger** (`ledger.csv`) | the merchant's own system | "I sold X for ₹gross" |
| **PG settlement** (`pg.csv`) | Razorpay | "I collected ₹gross, took ₹fee + ₹tax, refunded ₹r, paid you ₹net on date D" |
| **Bank statement** (`bank.csv`) | the merchant's bank | "₹amount credited on date D with narration N" |

They disagree constantly because of MDR fees, GST, refunds, chargebacks, `T+2`
settlement timing and bulk/split payouts.

---

## The pipeline, step by step

### 0 · Ingest & normalise  — `app/ingest/normalizer.py`
Each file has its own column names (`payment_id` vs `txn_id` vs `ref_no`, …).
The normaliser maps all three into one shape:

```
{ source, external_id, utr, amount_gross, fee, tax, amount_net,
  txn_date, settlement_date, narration, status }
```

The **raw rows are saved verbatim first** (`raw_records`) — nothing is ever
mutated, so any decision can be reconstructed later.

### 1 · Exact three-way match  — `app/matching/exact.py`  *(no AI)*
Join ledger ↔ PG ↔ bank on the strongest key (UTR / RRN), then check the amounts
tie out (`ledger.gross ≈ pg.gross`, `bank.net ≈ pg.net`) inside the settlement
window, **and** that the PG fee equals the contracted MDR + GST. All three agree
⇒ `auto_matched`. On realistic data this clears **85–95%** of volume. The AI
never sees these rows.

### 2 · Candidate generation  — `app/matching/candidates.py`  *(no AI)*
Every row that didn't exact-match becomes a **cluster anchor**. For each anchor
we score every possible counterpart from the other two sources on amount
closeness + date closeness + fuzzy text, and **force an exact UTR match to the
top**. Keep the best 6. Now each unresolved transaction is a little bundle:
`{ anchor, up to 6 candidates }`.

### 3a · Deterministic signals  — `app/matching/signals.py`  *(no AI — this is where accuracy comes from)*
`compute_signals()` turns the bundle into hard facts:

- is there a **same-UTR, amount-matched** ledger row? a bank row? (`ledger_matched`, `bank_matched`)
- `fee_overcharge_inr`, `net_short_inr`  (from a fee recompute)
- `bank_late_days`, `sla_breached`  (SLA measured against the batch's own latest date + 3 days, not the wall clock)
- `is_duplicate`

then applies an **ordered rule list** — first match wins:

```
duplicate?                          -> DUPLICATE
money row, no matching ledger?       -> MISSING_IN_LEDGER
PG fee over contract?                -> FEE_MISMATCH
net paid short, fee OK?              -> SHORT_SETTLEMENT
no bank credit, SLA breached?        -> MISSING_PAYOUT
no bank credit, still in SLA?        -> TIMING_GAP
bank credit arrived late?            -> TIMING_GAP
ledger + PG + bank all agree?        -> matched
otherwise                            -> unexplained
```

Output: a `suggested_verdict`, a `suggested_code`, and a
`suggested_amount_impact` (**Python owns every rupee figure**). On the benchmark
this scores **100% precision/recall on all seven outcomes**.

### 3b · Agent adjudication  — `app/agent/adjudicator.py`  *(AI — one LLM call per cluster)*
The LLM gets the anchor, the candidates and the whole `signals` object. It does
**not** classify — Python already did. It:

1. **confirms** the suggestion (→ confidence ≥ 0.9, the exception becomes
   eligible for auto-resolution), **or**
2. **disagrees**, naming the signal it thinks is wrong (→ confidence capped at
   0.55 → a human will look), and
3. writes the plain-English **`rationale`** and **`recommended_action`**.

Provider chain (all free tier, automatic failover):
`gemini/gemini-flash-latest → groq/qwen3.8-27b → groq/gpt-oss-120b →
openrouter/nemotron-3.5-lightning:free → openrouter/glm-5.2:free`.
No key configured, or unparseable output ⇒ Stage 3b is skipped and the
deterministic verdict is used directly, routed conservatively.

Every call is logged to `agent_runs` (model used, failover attempts, tokens,
latency, the signals it saw, the raw response).

### 4 · Routing  — `app/pipeline/routing.py`  *(no AI — this is CODE, not a prompt)*
An exception **auto-resolves** only if *all* hold:

- it has a concrete code
- the code is in the auto-resolve allow-list and **not** in `ALWAYS_HUMAN`
  (missing payout, short settlement, chargeback, missing-in-ledger, unexplained
  always go to a human)
- `confidence ≥ 0.90`  (i.e. the LLM confirmed)
- `|amount_impact| ≤ ₹500`

Everything else → **`pending_approval`** queue.

### 5 · Persistence & audit  — `app/db.py`, `app/audit/log.py`
`normalized_txns`, `match_groups`, `exceptions`, `agent_runs` and an
append-only `audit_log` (one entry per ingest / match / adjudication / route /
approval, with before/after snapshots) land in **MongoDB Atlas**.

### 6 · Human approval loop  — `app/api/routes.py` + the dashboard
The reviewer opens the queue, sees each exception with the agent's rationale,
evidence and recommended action, and clicks **approve / edit / reject**. Every
action appends to `audit_log`.

### 7 · Reporting  — `app/metrics/scorer.py`, `scripts/evaluate.py`
Against the synthetic `ground_truth.json`: auto-match rate, detection
precision/recall, per-code F1 + confusion matrix, money surfaced vs injected,
human-queue size, runtime — the exact numbers the Buildathon rubric asks for.

---

## What runs where

```
Next.js dashboard (Vercel)
      │  upload 3 files / view queue / approve
      ▼
FastAPI  (Hugging Face Spaces / Render)
      │  run_batch()  =  stages 0-6
      ├── deterministic core        (pandas/polars + rules)      ← no cost
      ├── ModelClient → free LLM     (Gemini → Groq → OpenRouter) ← free tier
      └── MongoDB Atlas M0           (all collections + audit)    ← free tier
```

Total running cost: **₹0**.

---

## The design rule that ties it together

> **Deterministic code makes every decision that touches money or gates an
> action. The LLM explains those decisions in human language and can raise its
> hand for review — it can never silently change one.**

That's what makes the accuracy reproducible, the audit trail trustworthy, and
the whole thing safe to show a finance team.

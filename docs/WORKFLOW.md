# ReconAgent — Workflow (explained simply)

## The lemonade-stand version

You run a stand. Three people hand you a notebook every day:

1. **Your notebook** (ledger): "Sold 100 cups at ₹10 = ₹1,000."
2. **Card-machine company's notebook** (PG settlement): "Collected ₹1,000, kept
   ₹20 fee + ₹3.60 tax, one kid got a ₹15 refund, sent you ₹961.40."
3. **Bank's notebook** (bank statement): "₹961.40 arrived today. Also ₹950 from
   two days ago."

Your job: make the three notebooks agree, and notice when they don't (missing
payout? overcharged fee? double entry?). ReconAgent is a robot that does this for
thousands of rows and only bothers you about the confusing ones.

## The six stages

```mermaid
sequenceDiagram
    participant U as Analyst
    participant P as Pipeline (code)
    participant A as Agent (LLM)
    participant DB as MongoDB
    participant Q as Approval queue

    U->>P: upload pg.csv, bank.csv, ledger.csv
    P->>DB: store raw rows (verbatim, immutable)
    P->>P: Stage 0 — normalise to common schema
    P->>P: Stage 1 — exact 3-way match (no LLM)
    P->>DB: match_groups (85–95% done here)
    P->>P: Stage 2 — build ≤3 candidates per leftover
    loop each unresolved cluster
        P->>A: anchor + candidates + tool report
        A->>A: pick match / classify exception / say "unexplained"
        A-->>P: Verdict {code, amount_impact, confidence, rationale, evidence}
        P->>P: Stage 4 — routing policy (pure code)
        alt high confidence + small ₹ + allowed code
            P->>DB: exception = auto_resolved (logged)
        else
            P->>Q: exception = pending_approval
        end
        P->>DB: audit_log + agent_runs
    end
    U->>Q: review exception (rationale + evidence)
    U->>DB: approve / edit / reject  ->  audit_log
    P->>U: metrics report
```

### Stage 0 — Normalise
Every source uses different column names. The normalizer maps them all to one
shape: `{utr, amount_gross, fee, tax, amount_net, txn_date, settlement_date,
narration, ...}`. Raw rows are stored untouched first.

### Stage 1 — Exact match (no LLM)
Join on the strongest key (UTR/RRN), then check amounts tie out within ₹1 and
dates fall inside the settlement window. Ledger + PG + Bank all agree ⇒
`auto_matched`. This clears the large majority. **The LLM never sees these rows.**

### Stage 2 — Candidate generation
For each leftover row, score every possible counterpart from the other sources on
three cheap signals — amount closeness, date closeness, fuzzy text similarity of
narration/IDs (optionally a semantic embedding score). Keep the top 3.

### Stage 3 — Agent adjudication (LLM, 1 call per cluster)
The agent gets the anchor row, its 3 candidates, and a **pre-computed tool
report** (expected fee, SLA check, duplicate check, date deltas). It returns:

| field | meaning |
| --- | --- |
| `verdict` | matched / exception / unexplained |
| `exception_code` | one of 10 taxonomy codes |
| `amount_impact` | rupees at stake |
| `direction` | merchant_owed / merchant_owes / neutral |
| `confidence` | calibrated 0–1 |
| `rationale` | ≤60 words, plain English, with numbers |
| `evidence` | which tool outputs / rows it used |
| `recommended_action` | e.g. "raise fee-dispute ticket for ₹2.00" |

The agent is told **not to do arithmetic** — it cites the tool report.

### Stage 4 — Routing (pure code, not the LLM)
Auto-resolve only if **all** are true:
- verdict is an exception with a concrete code
- code is in the auto-resolve allowlist and not in `ALWAYS_HUMAN`
- `confidence ≥ 0.90`
- `|amount_impact| ≤ ₹500`

Otherwise → **human approval queue**. A guardrail re-computes the money figure;
if the agent's number disagrees with Python's, confidence is capped and the item
goes to a human.

### Stage 5 — Human approval loop
Reviewer sees the agent's verdict, rationale and evidence; clicks approve / edit /
reject. Every action appends to `audit_log`. (Rejections become future training
examples — post-MVP.)

### Stage 6 — Reporting
Run against the synthetic `ground_truth.json` to produce hard numbers:
auto-match rate, classification precision/recall, ₹ surfaced, queue size, runtime.

## Exception taxonomy

| Code | Plain meaning | Auto-resolvable? |
| --- | --- | --- |
| `FEE_MISMATCH` | PG fee ≠ contracted MDR+GST | ✅ if small & confident |
| `TIMING_GAP` | Bank credit not in yet, still within SLA | ✅ |
| `DUPLICATE` | Same txn twice in one source | ✅ |
| `MISSING_PAYOUT` | Settled by PG, never hit bank, SLA breached | ❌ always human |
| `MISSING_IN_LEDGER` | Money in, no sale recorded | ❌ always human |
| `SHORT_SETTLEMENT` | Net < expected, unexplained | ❌ always human |
| `CHARGEBACK` | Negative adjustment = a dispute | ❌ always human |
| `REFUND` | Negative adjustment = a recorded refund | ✅ if matched |
| `FX_DIFF` | Currency conversion / rounding | review |
| `SPLIT_PAYOUT` | One bank credit = many PG lines | review |
| `UNEXPLAINED` | Agent can't account for it | ❌ always human |

## What "works without Claude / any one vendor" means here

1. Most of the pipeline is plain code — it needs no LLM at all.
2. The LLM step goes through `ModelClient`, which tries a **chain** of free
   providers (Gemini → Groq → OpenRouter free → GitHub Models) and fails over
   automatically.
3. If **no** provider is configured, the pipeline still completes — every
   unresolved cluster simply lands in the human queue instead of being
   pre-classified.

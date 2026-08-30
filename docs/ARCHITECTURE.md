# ReconAgent — Architecture

## 1. One-paragraph summary

ReconAgent is a batch finance-ops agent. A deterministic core ingests and
three-way matches transactions across a payment-gateway settlement report, a bank
statement and an internal ledger. Only the rows it *cannot* match deterministically
are handed to an LLM, which classifies each discrepancy into a fixed taxonomy,
verifies it with deterministic tools, and returns a schema-validated verdict with
a confidence score. A pure-code routing policy then decides — within explicit
rupee and confidence bounds — whether each verdict auto-resolves or goes to a
human approval queue. Every state transition is written to an append-only audit
log.

## 2. Component diagram

```mermaid
flowchart TD
    subgraph FE["Frontend — Next.js on Vercel"]
        U1[Upload 3 files]
        U2[Dashboard + metrics]
        U3[Approval queue]
        U4[Audit log viewer]
    end

    subgraph API["Backend — FastAPI on HF Spaces / Render"]
        R[/POST /batches/]
        RUN[Pipeline runner]
        Q[/GET exceptions · audit · approvals/]
    end

    subgraph CORE["Deterministic core — no LLM"]
        N[Normalizer]
        EM[Exact 3-way matcher]
        CG[Candidate generator<br/>amount · date · fuzzy · semantic]
        FEE[Fee recompute]
    end

    subgraph AGENT["Agent layer"]
        MC[ModelClient<br/>LiteLLM failover]
        AD[Adjudicator<br/>1 call / cluster]
        TL[Deterministic tools]
        MC --> AD
        TL --> AD
    end

    subgraph POLICY["Routing — pure code"]
        RT[route_verdict<br/>confidence + ₹ bounds]
    end

    subgraph DB["MongoDB Atlas (M0 free)"]
        D1[(raw_records)]
        D2[(normalized_txns<br/>+ vector index)]
        D3[(match_groups)]
        D4[(exceptions)]
        D5[(approvals)]
        D6[(audit_log)]
        D7[(agent_runs)]
    end

    subgraph LLMS["Free-tier LLM providers"]
        G[Gemini 2.5 Flash]
        GR[Groq Llama 3.3]
        ORF[OpenRouter :free]
        GH[GitHub Models]
    end

    U1 --> R --> RUN
    RUN --> N --> EM --> CG
    EM --> D3
    N --> D1 & D2
    CG --> AD
    FEE --> TL
    AD --> RT --> D4
    RT -->|pending| U3
    AD --> D7
    RUN --> D6
    MC -.-> G -.-> GR -.-> ORF -.-> GH
    U2 --> Q
    U3 --> D5
    U4 --> D6
```

## 3. The funnel (why cost stays near zero)

```mermaid
flowchart LR
    A[~500 transactions] --> B{Exact 3-way match}
    B -->|85–95%| C[auto_matched · 0 LLM calls]
    B -->|leftovers| D[Candidate generation]
    D --> E{Probabilistic + semantic score}
    E -->|clean single match| F[matched by agent · cheap]
    E -->|discrepancy| G[Agent classifies exception]
    G --> H{Routing policy}
    H -->|high conf + small ₹| I[auto_resolved · logged]
    H -->|else| J[Human approval queue]
```

Only **20–60 LLM calls** per 500-transaction batch → comfortably inside every
free tier.

## 4. Data model (MongoDB collections)

| Collection | Key fields | Notes |
| --- | --- | --- |
| `batches` | `_id`, summary metrics | one run |
| `raw_records` | `batch_id`, `source`, `payload` | **immutable**, verbatim rows |
| `normalized_txns` | common schema + `narration_embedding` | vector-search index on the embedding |
| `match_groups` | `ledger_txn_id`, `pg_txn_id`, `bank_txn_id`, `method` | `method` ∈ exact \| agent \| manual |
| `exceptions` | `code`, `amount_impact`, `confidence`, `rationale`, `evidence`, `routed_to` | one per unresolved cluster |
| `resolutions` / `approvals` | reviewer, decision, note | human loop |
| `audit_log` | `actor`, `action`, `before`, `after`, `created_at` | append-only |
| `agent_runs` | `model`, `attempts`, tokens, latency, `tool_calls`, `raw_response` | full LLM traceability |

### Why MongoDB here

- `raw_records` from three sources have **three different shapes** — documents
  store them with no schema gymnastics.
- The **aggregation pipeline** expresses reporting queries ("group settlement
  lines by UTR, sum net, compare to bank credit") concisely.
- **Atlas Vector Search** does semantic narration matching in the same engine —
  no second datastore.
- Multi-document transactions cover the audit-log write path.

Trade-off accepted: three-way relationship queries use `$lookup` rather than SQL
joins. For batch sizes in the thousands this is fine.

## 5. Provider-agnostic AI (no lock-in, no local model, no cost)

```mermaid
flowchart TD
    APP[adjudicator.py] --> MC[ModelClient.complete]
    MC --> C1{try LLM_PRIMARY}
    C1 -->|ok| OUT[ModelResult]
    C1 -->|429 / error| C2{try fallback 1}
    C2 -->|ok| OUT
    C2 -->|error| C3{try fallback 2 ...}
    C3 -->|all fail / no key| MU[[ModelUnavailable]]
    MU --> HUMAN[cluster -> approval queue]
```

- Config only: `LLM_PRIMARY`, `LLM_FALLBACKS` (comma-separated LiteLLM strings).
- No key configured ⇒ pipeline still runs; unresolved clusters route to a human.
- Swappable to a self-hosted model later by pointing at any OpenAI-compatible URL.

## 6. Deployment (all free tiers)

| Piece | Host | Free tier |
| --- | --- | --- |
| Frontend | Vercel Hobby | yes |
| Backend + agent | Hugging Face Spaces (Docker) or Render web service | yes |
| Database | MongoDB Atlas M0 | 512 MB |
| Batch queue (optional) | Upstash Redis | yes |
| CI + LLM fallback | GitHub Actions + GitHub Models | yes |

## 7. Security & correctness guardrails

1. **LLM never does arithmetic** — it cites tool outputs; Python owns every number.
2. **Money figure cross-check** — agent's `amount_impact` is re-derived from the
   tool report; a mismatch caps confidence and forces a human.
3. **Routing is code, not prompt** — confidence + rupee ceiling + code allowlist.
4. **`ALWAYS_HUMAN` codes** (missing payout, chargeback, short settlement,
   missing-in-ledger, unexplained) never auto-resolve.
5. **Immutable raw + append-only audit** — every decision is reconstructable.
6. **No secrets in code** — all keys via env; `.env` git-ignored.

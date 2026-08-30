# ReconAgent — AI Integration

## 1. Where AI is used (and where it deliberately is not)

| Task | Handled by | Why |
| --- | --- | --- |
| Parsing / normalising files | code | deterministic, testable |
| Exact three-way match | code | it's a join, not a judgement |
| Candidate scoring (amount/date/fuzzy) | code | cheap, explainable |
| Semantic narration similarity | **embeddings** | bank narration strings are natural language |
| Deciding which candidate is the real match | **LLM** | fuzzy, context-dependent |
| Classifying the discrepancy | **LLM** | maps messy reality → taxonomy |
| Arithmetic / money figures | code (tools) | LLMs must not be trusted with numbers |
| Auto-resolve vs human | code (routing policy) | must be auditable and bounded |

> Principle: **the model is the detective who reads clues and writes the report;
> it never operates the calculator or the cash register.**

## 2. The agent contract

One LLM call per unresolved cluster. Stateless. Input:

```json
{
  "taxonomy": { "FEE_MISMATCH": "PG fee differs from contracted MDR+GST", ... },
  "anchor":   { "id": "...", "source": "pg", "gross": 1000, "fee": 25, "net": 971.4, ... },
  "candidates": [ { "id": "...", "source": "bank", "net": 971.4, ... } ],
  "tool_report": {
    "recompute_expected_fee(anchor)": { "expected_fee": 20.0, "net_delta_short_paid": 5.0, ... },
    "within_settlement_sla(anchor)":  { "age_days": 6, "within_sla": false },
    "check_duplicate(anchor)":        { "is_duplicate": false },
    "candidates": [ { "id": "...", "match_score": 0.91, "date_delta_days": {"days": 4} } ]
  }
}
```

Required output (validated against `models.Verdict`):

```json
{
  "verdict": "exception",
  "match_group": ["pg:12", "bank:home"],
  "exception_code": "FEE_MISMATCH",
  "amount_impact": 5.00,
  "direction": "merchant_owed",
  "confidence": 0.93,
  "rationale": "Contract MDR 2% => expected fee ₹20.00; PG charged ₹25.00. Net ₹5.00 short vs tool report. Bank credit matches PG net exactly.",
  "evidence": ["recompute_expected_fee(anchor).net_delta_short_paid=5.0", "candidate bank:home match_score=0.91"],
  "recommended_action": "Raise fee-dispute ticket for ₹5.00"
}
```

## 3. Provider strategy — free, hosted, no lock-in

`ModelClient` wraps [LiteLLM](https://github.com/BerriAI/litellm). One uniform
call shape; the model is a string.

```
LLM_PRIMARY   = gemini/gemini-2.5-flash                    # best free quality
LLM_FALLBACKS = groq/llama-3.3-70b-versatile,              # fastest
                openrouter/qwen/qwen-2.5-72b-instruct:free,# free
                github/gpt-4o-mini                          # free preview
```

Failover order on rate-limit or error: primary → each fallback → `ModelUnavailable`.

| Provider | Free tier | Role |
| --- | --- | --- |
| Google AI Studio (Gemini) | generous RPM/day, no card | primary — reasoning + JSON |
| Groq | daily allowance, no card | speed / first fallback |
| OpenRouter `:free` models | modest daily cap | free fallback |
| GitHub Models | free preview, GitHub account | fallback + CI |
| Hugging Face Inference | small monthly credit (already authed) | experimentation |

**No local model. No paid API. No single vendor.** Swapping to a self-hosted
OpenAI-compatible endpoint later is a one-line config change.

## 4. Staying inside free limits

1. **Deterministic core first** — LLM only sees 4–12% of rows.
2. **Pre-computed tool report** — usually one round-trip per cluster, no
   multi-step tool-calling loop.
3. **Response cache** — identical cluster fingerprint reuses the prior verdict.
4. **Optional triage model** (`LLM_TRIAGE`, e.g. `gemini-2.0-flash`) does a
   cheap "is this even ambiguous?" pass before the stronger model.
5. **Low concurrency + backoff** on 429s; failover absorbs the rest.

Budget: 500-txn batch ≈ 20–60 completion calls ≈ well under any one provider's
daily free quota.

## 5. Embeddings (semantic narration matching)

- `EMBEDDINGS_MODEL` (default `gemini/text-embedding-004`, free).
- Each `normalized_txns.narration` is embedded once at ingest.
- Atlas Vector Search index on `narration_embedding` (cosine).
- Candidate generator adds a `semantic` signal alongside the fuzzy score, so a
  bank line reading `NEFT/RZPY/ACME-SEP03` still matches the `ACME` Sept-3 batch
  even with no shared token.
- Disable by leaving `EMBEDDINGS_MODEL` blank — pipeline falls back to RapidFuzz.

## 6. Safety / trust checklist

- [x] LLM output is schema-validated before use.
- [x] `amount_impact` re-derived in code; disagreement caps confidence + forces human.
- [x] Routing decision is code, not model output.
- [x] `ALWAYS_HUMAN` taxonomy codes can never auto-resolve.
- [x] Every LLM call logged to `agent_runs` (model, attempts, tokens, latency,
      tool inputs, raw response).
- [x] Pipeline fully functional with the LLM disabled.
- [x] No secrets in code; keys via env only.

## 7. What we'd add post-hackathon

- Reviewer-rejection feedback → few-shot examples per taxonomy code.
- Confidence calibration curve from labelled history.
- Multi-step tool-calling for `SPLIT_PAYOUT` grouping.
- Self-hosted open model behind the same `ModelClient` for on-prem deployments.

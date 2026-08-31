# ReconAgent — AI Integration

## 1. Where AI is used (and where it deliberately is not)

| Task | Handled by | Why |
| --- | --- | --- |
| Parsing / normalising files | code | deterministic, testable |
| Exact three-way match | code | it's a join, not a judgement |
| Candidate scoring (amount/date/fuzzy/UTR) | code | cheap, explainable |
| **Classifying the discrepancy** (`compute_signals`) | **code** | UTR-linked rules are exact and auditable |
| Arithmetic / money figures | code | LLMs must not be trusted with numbers |
| Confirming the classification + writing the rationale | **LLM** | natural-language explanation; a second pair of eyes |
| Flagging a disagreement for a human | **LLM** | catches cases the rules don't cover |
| Auto-resolve vs human | code (routing policy) | must be auditable and bounded |

> Principle: **Python decides the money; the LLM explains it and can raise a
> hand.** The model never operates the calculator or the cash register.

## 2. The agent contract

One LLM call per unresolved cluster. Stateless. Input — the anchor, its
candidates, and the full **deterministic `signals`** object (this is the key
part: Python has already classified the cluster):

```json
{
  "anchor":   { "id": "pg:12", "source": "pg", "gross": 1000, "fee": 25, "net": 971.4, ... },
  "candidates": [ { "id": "bank:77", "source": "bank", "net": 971.4, "match_score": 1.83 }, ... ],
  "signals": {
    "ledger_matched": true, "bank_matched": true, "bank_late_days": 0,
    "sla_breached": false, "is_duplicate": false,
    "fee_overcharge_inr": 5.0, "net_short_inr": 5.0,
    "suggested_verdict": "exception", "suggested_code": "FEE_MISMATCH",
    "suggested_amount_impact": 5.0, "reason": "PG fee over contract by 5.0"
  }
}
```

Output (the LLM never sets `amount_impact` — Python keeps
`signals.suggested_amount_impact`):

```json
{
  "verdict": "exception",
  "exception_code": "FEE_MISMATCH",
  "confidence": 0.95,
  "rationale": "Contract MDR 2% => expected fee INR 20.00; PG charged INR 25.00, so net is INR 5.00 short. Bank credit equals the reduced PG net exactly.",
  "recommended_action": "Raise a fee-dispute ticket for INR 5.00"
}
```

- LLM `verdict` + `exception_code` **equal** the suggestion -> confidence lifted
  to >= 0.9, the exception is eligible for auto-resolution.
- LLM **disagrees** -> confidence capped at 0.55, rationale records the
  disagreement, routing sends it to a human.
- LLM output unparseable / no LLM configured -> deterministic verdict is used as
  is, routed conservatively.

## 3. Provider strategy — free, hosted, no lock-in

`ModelClient` wraps [LiteLLM](https://github.com/BerriAI/litellm). One uniform
call shape; the model is a string.

```
LLM_PRIMARY   = gemini/gemini-flash-latest                       # best free quality + JSON
LLM_FALLBACKS = groq/qwen/qwen3.8-27b,                           # fast, clean JSON
                groq/openai/gpt-oss-20b,                         # fast, different family
                openrouter/nvidia/nemotron-3.5-lightning:free,   # fast agentic MoE, free
                openrouter/z-ai/glm-5.2:free                     # strong, often rate-limited
```

Failover order on rate-limit or error: primary → each fallback → `ModelUnavailable`.
Per-attempt timeout is 45 s so a hung provider fails over fast.

> **Model IDs drift.** The vendors rotate model names every few months
> (`gemini-2.5-flash`, `llama-3.3-70b-versatile` and `qwen-2.5-72b:free` were all
> retired by mid-2026). Re-check with:
> `curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"`,
> `curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY"`,
> `curl -s https://openrouter.ai/api/v1/models` (filter `pricing.prompt == "0"`).

### What kind of model this task needs

Cluster adjudication is a **classify-and-fill-the-form** job, not open-ended
generation. The model must be good at:

1. **Instruction-following + strict JSON / structured output** — it must return
   the `Verdict` schema every time.
2. **Tool-grounded reasoning** — use the numbers in the tool report, never
   compute or invent them.
3. **Short discriminative reasoning over a fixed label set** (the 10 taxonomy
   codes) with a *calibrated* confidence.
4. **Speed + cheap** — it's called 20–60× per batch.

It does **not** need: long context, creativity, coding, vision, multilinguality,
or long chain-of-thought (reasoning models that emit a visible "thinking"
preamble, like Nemotron *Lightning*, actually hurt here — the JSON parser has a
fallback for them but they belong low in the chain).

So the sweet spot is a **small-to-mid instruction-tuned "agentic" model with a
JSON mode**: Gemini Flash, Qwen-3 27B, GPT-OSS-20B, Llama-class 8–70B. Big
frontier models are overkill; tiny 1–3B models miss the subtle cases (which is
fine — those fall below the confidence threshold and route to a human anyway).

| Provider | Free tier | Role in the chain |
| --- | --- | --- |
| Google AI Studio (Gemini) | generous RPM/day, no card | primary — best reasoning + JSON |
| Groq | daily allowance, no card | fast fallbacks (Qwen-3, GPT-OSS) |
| OpenRouter `:free` models | modest daily cap | free fallbacks (Nemotron, GLM) |
| GitHub Models | **closed to new signups (Jun 2026)** | only if you already have access |
| Hugging Face Inference | small monthly credit (already authed) | experimentation |

**No local model. No paid API. No single vendor.** Swapping to a self-hosted
OpenAI-compatible endpoint later is a one-line config change.

### GitHub Models — status & how to get a token

As of mid-2026 GitHub Models is **closed to new customers**; only accounts with
prior active usage keep API access (playground + REST API + `.prompt.yml`). New
users are pointed to Azure AI Foundry or Copilot's token-metered API. That's why
it is **not** in the default chain.

If your account already has access:

1. github.com → **Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token**.
2. Under **Permissions → Account permissions**, grant **Models: read-only**.
   (Classic tokens: the `models` scope.)
3. Copy the token into `.env` as `GITHUB_MODELS_TOKEN=...` and append
   `github/gpt-4o-mini` (or `github/gpt-4o`) to `LLM_FALLBACKS`.
4. Free-tier limits for existing users: ~50 req/day for high-tier models,
   ~150/day for mini, 8k in / 4k out per request.

## 4. Staying inside free limits

1. **Deterministic core first** — LLM only sees 4–12% of rows.
2. **Pre-computed tool report** — usually one round-trip per cluster, no
   multi-step tool-calling loop.
3. **Response cache** — identical cluster fingerprint reuses the prior verdict.
4. **Optional triage model** (`LLM_TRIAGE`, e.g. `gemini/gemini-flash-lite-latest`)
   does a cheap "is this even ambiguous?" pass before the stronger model.
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

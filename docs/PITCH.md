# ReconAgent — 5-minute pitch

Razorpay AI Buildathon · Track 04 (AI Finance Controller)

**One line:** ReconAgent is an autonomous finance controller that does three-way
payment reconciliation end to end — it matches the money, explains every
mismatch, fixes the safe ones itself, and escalates the rest with a full audit
trail.

---

## The script (with on-screen cues)

### 0:00 – 0:35 · The problem

> Every business that takes online payments runs the same painful monthly
> ritual. You have three records of the same money: your **sales ledger**, the
> **payment gateway's settlement report**, and your **bank statement**. They
> never agree. Fees, GST, FX, refunds, chargebacks, T+2 settlement timing,
> split payouts — a few hundred transactions become a day of an analyst
> cross-checking spreadsheets, and small leaks (an over-charged fee here, a
> payout that never landed there) go unnoticed for months.

*On screen: the three files open side by side — a Razorpay recon CSV, an MT940
bank statement, a Zoho ledger export. Visibly different formats.*

### 0:35 – 1:20 · The insight

> ReconAgent treats this as a controller problem, not a chatbot problem. The
> rule is simple: **Python decides the money. The LLM explains it and can raise
> a hand.** Deterministic code does the matching and the arithmetic — it's
> exact and auditable. The language model never changes a number or a
> classification; it writes the human rationale, drafts the recommended action,
> and flags when a figure looks wrong. Then a **bounded policy** — pure code —
> decides what auto-resolves: only high confidence, only small rupee impact,
> only safe exception types. Everything else goes to a human queue.

*On screen: the architecture diagram from `docs/ARCHITECTURE.md` — the funnel.*

### 1:20 – 3:45 · Live demo

*On screen: the deployed dashboard.*

1. **New batch → "Run a sample dataset"** → pick `IN-d2c-hdfc`.
   > This is a real-format Razorpay settlement report, an HDFC bank statement,
   > and a Zoho ledger — 400 payments, with defects injected against a known
   > ground truth. I'll run the whole pipeline live.

2. **Batch dashboard loads.**
   > ~92% auto-matched with zero AI — deterministic UTR matching and fee
   > verification. Runtime is seconds. The region and currency are detected
   > from the files; so are all three formats.

   *Point at: auto-match rate, the funnel, "exceptions by type" donut, "rupees
   at risk" bars, the quality-gate bullets.*

3. **Open one exception in the queue** (e.g. a `FEE_MISMATCH`).
   > Here's the deterministic signal — contracted MDR is 2%, expected fee
   > ₹20.00, the gateway charged ₹25.00. The LLM confirmed that and wrote this
   > rationale. Confidence 0.95, impact ₹5.00, inside the auto-resolve bounds —
   > so it resolved itself.

4. **Open a `MISSING_PAYOUT`.**
   > A whole settlement batch's bank credit never arrived, 25 days past the T+2
   > SLA. This code is on the always-human list — it never auto-resolves,
   > regardless of confidence. It's in the queue with the escalation drafted.

5. **Approve one item.** → **Audit tab.**
   > Every step — ingest, match, each adjudication, the routing decision, my
   > approval just now — is an append-only audit entry. This is what makes it a
   > controller and not a suggestion box.

6. *(Optional)* **Switch region to US, run `US-saas-camt`.**
   > Same engine. Stripe balance report, ISO 20022 CAMT.053 bank file, USD, no
   > GST on fees, ACH trace numbers instead of UTRs, cross-border FX lines
   > flagged as `FX_DIFF`. IN, US and EU are all supported, fully
   > multi-currency.

### 3:45 – 4:40 · How it holds up

> - **10-code exception taxonomy**, deterministic classifier — 100% per-code F1
>   on the benchmark.
> - Across the committed sample datasets: **auto-match 92–94%**, detection
>   **recall 0.79–1.00**, **precision 0.96–1.00**.
> - Concurrency took a 500-transaction batch from **730 s to 13.5 s**.
> - **Provider-agnostic** LLM: a LiteLLM failover chain across Gemini, Groq and
>   OpenRouter free tiers. No single vendor, no local model. With **no key at
>   all**, it still runs and routes everything to the queue.
> - **₹0 running cost** — MongoDB Atlas M0, free LLM tiers, Vercel + Render
>   free dynos.

### 4:40 – 5:00 · Close

> ReconAgent is the finance-ops equivalent of CI: it runs on every settlement
> period, clears the routine 90%, and hands a human a short, explained,
> audited queue of the things that actually need judgment. That's the AI
> Finance Controller.

---

## Judge's cheat sheet

| Question | Answer |
| --- | --- |
| Is the AI making financial decisions? | No. Python matches and computes; the policy that auto-resolves is pure code. The LLM writes explanations and can flag disagreement. |
| What if the LLM hallucinates a number? | `amount_impact` is recomputed in Python from cited figures; a mismatch force-routes to a human. |
| What if all LLM providers are down? | Deterministic verdict path; everything unresolved → human queue. Nothing breaks. |
| Vendor lock-in? | LiteLLM model strings, 5-deep failover across 3 providers, swappable via env. |
| Real data? | Real *formats* (Razorpay recon, Stripe balance, SWIFT MT940, ISO 20022 CAMT.053, HDFC/ICICI/Chase CSV, Zoho) and real *economics* (MDR by method, GST, FX spread, TDS, rolling reserve, T+n + weekend roll) — calibrated to public NPCI/RBI data. No confidential third-party numbers. |
| Cost to run? | ₹0 — all free tiers. |
| Geographies? | IN / US / EU, full multi-currency with per-region tax and MDR rules. |

---

## Demo runbook (do this before recording)

1. Deploy per [`DEPLOY.md`](DEPLOY.md), or run locally:
   ```bash
   # backend
   cd backend && uvicorn app.main:app --port 8000
   # frontend
   cd frontend && npm run dev
   ```
2. Open `http://localhost:3000`, hit **Run a sample dataset → IN-d2c-hdfc**,
   confirm the batch dashboard renders a real result (not the "Demo mode" badge).
3. Pre-pick the two exceptions you'll open so you're not hunting on camera.
4. If recording offline: the dashboard falls back to bundled demo data with no
   backend at all — every screen still works, it just shows the "Demo mode"
   badge and the fixed sample batch.
5. Keep it to 5:00. The demo (section 3) is the part that wins; don't overrun
   the setup.

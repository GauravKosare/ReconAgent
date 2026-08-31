# ReconAgent — Data Model & Realistic Datasets

ReconAgent has **two** data generators:

| Generator | Purpose | Formats | Bank payouts |
| --- | --- | --- | --- |
| `data/generator/generate_dataset.py` | CI regression fixture — small, stable, deterministic | 3 simple CSVs | one per transaction (toy) |
| `data/realworld/` | **realistic simulation** of what a finance team actually receives | real settlement / bank / ledger formats | **aggregated** — one bank credit per settlement batch |

The realistic generator is what "simulate the actual working" means: real formats,
real money mechanics, and aggregated bank payouts that force **settlement-batch
reconciliation** (1 bank credit ↔ many PG lines), not 1:1 toy matching.

---

## 0. Geography — IN, US, EU

`--region` (default `IN`) picks the jurisdiction. Every layer changes with it:

| | **IN** | **US** | **EU (DE)** |
| --- | --- | --- | --- |
| Currency | INR | USD | EUR |
| Tax on the processing fee | **18% GST, charged** | **none** (services not sales-taxed) | **VAT-exempt** — payment processing is a financial service (Dir. 2006/112/EC Art. 135) |
| MDR norms | capped; UPI ~0, cards ~2% | uncapped; ~1.8–2.9% + $0.30 | **IFR-capped** (Reg. 2015/751): consumer cards ~0.2–1.2% |
| Methods | UPI / card / netbanking / wallet | card / ACH / wallet | card / SEPA / iDEAL / wallet |
| Settlement | T+2, rails UPI/NEFT/IMPS/RTGS | T+2 ACH, rails ACH/WIRE/RTP | T+1 SEPA, rails SEPA/SEPA_INSTANT/TARGET2 |
| Payment reference | UTR (12-digit) | ACH trace (15-digit) | End-to-End ID |
| Number / date | `1,23,456.78` · dd/mm/yy | `1,234.56` · mm/dd/yyyy | `1.234,56` · `;`-delimited · dd.mm.yyyy |
| Default PG report | Razorpay recon | Stripe balance report | Stripe balance report |
| Default bank format | HDFC CSV | Chase-style CSV | CAMT.053 XML |

The backend keeps its own copy of the reconciler-relevant facts in
`app/matching/region_rules.py` (so it has no dependency on the generator).

### Multi-currency (full)

A configurable share of card payments (5% IN → 18% EU) are **presented in a
foreign currency** and converted at settlement: `settled = presentment ×
mid_rate × (1 − spread)`, spread ~2%. The PG report carries both amounts + the
effective rate; the bank shows only the settlement currency. The reconciler:

- infers each method's contract fee (`fee = pct·gross + flat`, robust linear fit
  over domestic payments — no per-merchant config)
- for a cross-border line, widens the fee tolerance by the contracted FX spread
- flags **`FX_DIFF`** when the conversion + fee kept exceeds the contracted spread

## 1. Real file formats

### Payment gateway — Razorpay Settlement Recon Report (`pg_settlement_recon.csv`)

Exact schema from the [Razorpay recon API](https://razorpay.com/docs/api/settlements/fetch-recon/):

```
entity_id,type,debit,credit,amount,currency,fee,tax,on_hold,settled,created_at,
settled_at,settlement_id,posted_at,credit_type,description,notes,payment_id,
settlement_utr,order_id,order_receipt,method,card_network,card_issuer,card_type,dispute_id
```

Real quirks reproduced:
- **amounts in paise** (integer subunits) — the parser converts to rupees
- **unix timestamps** for `created_at` / `settled_at`
- **`settlement_utr` is shared** by every line in one settlement batch
- refunds carried as `type=refund` with the value in `debit`
- the international transaction fee is folded into `fee` so `net = amount − fee − tax` always holds

### Bank statement — four real formats (pick with `--bank`)

| `--bank` | Format | Notes |
| --- | --- | --- |
| `mt940` | SWIFT **MT940** | `:20:` `:25:` `:28C:` `:60F:` `:61:` `:86:` `:62F:` tags; amounts with `,` decimal |
| `camt` | ISO 20022 **camt.053.001.02** | XML — `<Ntry>` / `<Amt>` / `<CdtDbtInd>` / `<ValDt>` / `<RmtInf>` |
| `hdfc` | **HDFC Bank** CSV | `Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance` |
| `icici` | **ICICI Bank** CSV | `S No.,Value Date,...,Transaction Remarks,Withdrawal Amount (INR ),Deposit Amount (INR ),Balance (INR )` |

All are **aggregated payouts** — one credit per settlement batch. Route splits
appear as 2–3 credits that reference the same settlement UTR. Narrations use real
rail conventions (`NEFT CR-HDFC0000123-<MERCHANT>-<UTR>`, `MMT/IMPS/<UTR>/...`,
`RTGS CR-...`). Terse RTGS lines sometimes carry no clean UTR — the reconciler
falls back to an amount + date-window match for those.

### Internal ledger — Zoho Books style (`ledger_zoho.csv`)

```
Invoice Number,Invoice Date,Order ID,Reference Number,Customer Name,
Place of Supply,Invoice Status,Payment Mode,Total,Currency
```

No UTR — joins to the PG report on `Order ID` / `Reference Number`.

---

## 2. Money mechanics (`data/realworld/economics.py`)

Calibrated to public Indian digital-payments data (NPCI UPI statistics, RBI
payment-system reports, published aggregator MDR schedules). Parameters, not
precision claims — the point is the **shape** matches production.

- **Method mix** per profile (UPI ~60–70%, card, netbanking, wallet)
- **MDR by method**: UPI 0%, card ~1.9%, wallet ~1.7%, netbanking flat ₹12; **18% GST** on the fee
- **International cards**: 3% forex markup + 0.5% cross-border fee, some settled in USD
- **Settlement cycles**: T+1 / T+2 / T+3 by profile, plus instant settlement, with **weekend/holiday roll-forward**
- **Refunds** posted as negative entries in the same settlement batch
- **Marketplace**: 1% **TDS** (§194-O) + 5% **rolling reserve** withheld from payouts; **Route split** payouts
- **Chargebacks**: 2-cycle lifecycle with reserve hold (modelled in the scenario, light touch in v1)

### Business profiles (`--profile`)

| Profile | AOV median | Mix skew | Settlement | Extras |
| --- | --- | --- | --- | --- |
| `d2c-brand` | ₹899 | UPI-heavy | T+2 + instant | — |
| `saas` | ₹2,499 | card-heavy | T+2 | more international |
| `marketplace` | ₹649 | UPI-heavy | T+1 | TDS + reserve + Route splits |
| `travel` | ₹7,999 | card-heavy | T+3 | reserve, high refunds, international |

---

## 3. Injected defects & ground truth

`ground_truth.json` — one row per payment: `{order_id, order_receipt,
settlement_utr, expected_code, gross, expected_net, actual_net,
injected_impact_inr}`. `expected_code` is `null` for a clean transaction.

| Code | Injected as | Level |
| --- | --- | --- |
| `FEE_MISMATCH` | PG fee above the contracted MDR | per line |
| `SHORT_SETTLEMENT` | unexplained net deduction, fee correct | per line |
| `MISSING_IN_LEDGER` | payment + payout exist, no ledger row | per line |
| `DUPLICATE` | webhook double-fired the ledger row | per line |
| `MISSING_PAYOUT` | whole settlement batch's bank credit never arrived, SLA breached | per batch |
| `TIMING_GAP` | bank credit arrived 7–11 days late | per batch |
| `SPLIT_PAYOUT` | a Route split leg is missing so the parts don't sum | per batch |

---

## 4. Running it

```bash
# generate (region picks currency, formats, tax, MDR — --pg/--bank override)
python -m data.realworld.generate --region EU --profile saas --payments 500 \
    --out data/samples/realworld/EU --seed 7

# reconcile one batch (formats auto-detected)
python scripts/run_batch.py --realistic --region EU \
    --pg     data/samples/realworld/EU/pg_stripe_balance.csv \
    --bank   data/samples/realworld/EU/bank_statement.camt053.xml \
    --ledger data/samples/realworld/EU/ledger_export.csv --no-persist

# score across seeds
python scripts/evaluate_realworld.py --region US --profile d2c-brand --seeds 1,2,3
```

### Committed sample datasets

`data/samples/realworld/` holds **11 datasets** covering every region, four
merchant profiles, and every statement format (Razorpay recon · Stripe balance ·
MT940 · CAMT.053 · HDFC / ICICI / Chase-style CSV). See
[`data/samples/realworld/README.md`](../data/samples/realworld/README.md) for the
matrix. Regenerate with `python scripts/gen_samples.py`; each is round-tripped
end-to-end by `backend/tests/test_realworld.py::test_sample_dataset`.

### Pipeline (`app/pipeline/realistic.py`)

```
detect_and_parse  →  reconcile_settlements  →  batch outcomes + per-line issues
                          │
          ┌───────────────┴────────────────┐
   batch didn't reconcile            line not clean
   MISSING_PAYOUT / TIMING_GAP       FEE_MISMATCH / MISSING_IN_LEDGER
   SPLIT_PAYOUT / SHORT_SETTLEMENT   SHORT_SETTLEMENT / DUPLICATE
          └───────────────┬────────────────┘
                    LLM writes rationale + can flag  →  routing  →  scorecard
```

`reconcile_settlements` groups PG lines by `settlement_id`, sums the net, and
matches that to the bank credit(s) for the same `settlement_utr` (summing Route
splits). Within a reconciled batch each PG line is matched to its ledger row on
the order id.

---

## 5. Current results (deterministic, no LLM)

Across the 7 "strong" committed sample datasets (d2c / saas / travel, all three
regions, every format):

| | range |
| --- | --- |
| Auto-match rate | **0.92 – 0.94** |
| Detection recall | **0.79 – 1.00** |
| Detection precision | **0.96 – 1.00** |

Per-code F1 is strong for `DUPLICATE`, `MISSING_IN_LEDGER`, `TIMING_GAP`,
`MISSING_PAYOUT` and mostly for `FEE_MISMATCH` / `SHORT_SETTLEMENT`.

**Known gaps (next tuning items):**
- `FX_DIFF` on small US transactions — a 1–2% FX overcharge on a $4–40 payment is
  cents, near the noise floor; needs a signed rate check against a reference feed.
- `SPLIT_PAYOUT` recall on US/EU — the batch-level split heuristic misses some
  organic-vs-defect splits.
- `marketplace` profile — TDS/reserve percentages must be passed to
  `run_realistic_batch(tds_percent=…, reserve_percent=…)`; the estimate drifts on
  large batches.

The **detection layer** (is this order an exception at all?) is solid across all
three regions; per-code **classification** of the rarer batch/FX codes is the
work that remains.

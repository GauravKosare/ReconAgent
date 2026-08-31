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
# generate
python -m data.realworld.generate --profile d2c-brand --payments 500 \
    --bank hdfc --out data/samples/realworld --seed 7

# reconcile one batch
python scripts/run_batch.py --realistic \
    --pg data/samples/realworld/pg_settlement_recon.csv \
    --bank data/samples/realworld/bank_statement_hdfc.csv \
    --ledger data/samples/realworld/ledger_zoho.csv --no-persist

# score across seeds
python scripts/evaluate_realworld.py --profile d2c-brand --payments 500 \
    --bank hdfc --seeds 1,2,3
```

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

| Profile / bank | Auto-match | Detection recall | Detection precision |
| --- | --- | --- | --- |
| d2c-brand / HDFC | ~93% | 100% | 100% |
| d2c-brand / MT940 | ~93% | 100% | 100% |
| saas / CAMT.053 | ~94% | ~97% | ~97% |
| travel / MT940 | ~85% | ~98% | 100% |
| **marketplace / ICICI** | ~69% | 100% | **~50%** |

**Known gap:** `marketplace` + `icici` is the hard case — terse ICICI RTGS lines
(no UTR) plus TDS/reserve estimation drift on large batches plus Route splits.
The TDS/reserve percentages must be told to the reconciler
(`run_realistic_batch(tds_percent=…, reserve_percent=…)`); the estimate is
approximate. Tightening this is the next tuning item for the realistic path.

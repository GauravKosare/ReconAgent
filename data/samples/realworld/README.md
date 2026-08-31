# Sample datasets — `data/samples/realworld/`

Committed reconciliation datasets covering every region, several merchant
profiles, and every statement format. Regenerate with `python scripts/gen_samples.py`.

Each folder has the three source files + `ground_truth.json` + `dataset_manifest.json`.

| Folder | Region | Profile | Ccy | Formats | Payments | Cross-border | Injected defects |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IN-d2c-hdfc` | IN | d2c-brand | INR | razorpay + hdfc | 400 | 12 | 37 |
| `IN-saas-mt940` | IN | saas | INR | razorpay + mt940 | 350 | 9 | 35 |
| `IN-travel-icici` | IN | travel | INR | razorpay + icici | 350 | 8 | 36 |
| `IN-marketplace-hdfc` | IN | marketplace | INR | razorpay + hdfc | 400 | 15 | 36 |
| `US-d2c-chase` | US | d2c-brand | USD | stripe + us_csv | 400 | 44 | 34 |
| `US-saas-camt` | US | saas | USD | stripe + camt | 400 | 58 | 35 |
| `US-travel-chase` | US | travel | USD | stripe + us_csv | 300 | 40 | 27 |
| `EU-d2c-camt` | EU | d2c-brand | EUR | stripe + camt | 400 | 47 | 41 |
| `EU-saas-mt940` | EU | saas | EUR | stripe + mt940 | 350 | 62 | 36 |
| `EU-travel-camt` | EU | travel | EUR | stripe + camt | 350 | 55 | 34 |
| `EU-marketplace-camt` | EU | marketplace | EUR | stripe + camt | 400 | 49 | 35 |

Run one:

```bash
python scripts/run_batch.py --realistic --region EU \
  --pg     data/samples/realworld/EU-d2c-camt/pg_stripe_balance.csv \
  --bank   data/samples/realworld/EU-d2c-camt/bank_statement.camt053.xml \
  --ledger data/samples/realworld/EU-d2c-camt/ledger_export.csv --no-persist
```

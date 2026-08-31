# ReconAgent — Dashboard

Next.js 15 (App Router) + Tailwind. A business analytics dashboard for the
reconciliation agent: KPI cards, resolution funnel, exception approval queue,
and an append-only audit timeline.

## Design

- **Style:** modern B2B SaaS — frosted cards (`.glass`), soft depth, dense
  dashboard spacing. Light + dark via `prefers-color-scheme`.
- **Palette:** trust blue `#2563EB` primary, orange `#EA580C` for the single
  primary CTA, slate neutrals, semantic green/amber/red for status.
- **Type:** Calistoga (display numbers/headings) · Inter (body) · JetBrains Mono
  (IDs, UTRs, amounts).
- Guidance sourced from the `ui-ux-pro-max` skill (`--design-system` +
  `--domain chart` / `--stack nextjs`).

## Screens

| Route | Purpose |
| --- | --- |
| `/` | Overview — hero, latest-batch KPIs, recent-batches table |
| `/upload` | Drop the 3 CSVs, run a batch (or open the demo) |
| `/batches/[id]` | Batch dashboard — KPI stats, resolution funnel, exceptions donut, ₹-at-risk bars, quality-gate bullets |
| `/batches/[id]/queue` | Approval queue — filterable, each exception expands to the agent rationale + evidence + Approve / Edit / Reject |
| `/batches/[id]/audit` | Audit log — actor-coded timeline with the `after` payload of every entry |

## Running

```bash
npm install
cp .env.local.example .env.local          # set NEXT_PUBLIC_API_URL (default http://localhost:8000)
npm run dev                                # http://localhost:3000
```

**Offline demo:** if the API is unreachable the dashboard renders from a bundled
sample batch (`lib/sample.ts`) and shows a "Demo mode" badge — so the pitch video
works with no backend. Point `NEXT_PUBLIC_API_URL` at a running FastAPI instance
for live data.

## Deploy

Vercel (Hobby, free). Set `NEXT_PUBLIC_API_URL` to the deployed backend URL.

# ReconAgent — Frontend

Next.js 15 (App Router) + Tailwind + shadcn/ui dashboard.

## Screens

| Route | Purpose |
| --- | --- |
| `/` | Upload the three files, trigger a batch, show progress |
| `/batches/[id]` | Summary cards: auto-match rate, exceptions by code, ₹ flagged, runtime |
| `/batches/[id]/queue` | Approval queue — each exception with agent rationale + evidence + Approve / Edit / Reject |
| `/batches/[id]/audit` | Chronological audit log viewer |
| `/batches/[id]/report` | Metrics report (Recharts) — auto vs manual, precision/recall vs ground truth |

## Setup

```bash
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL
npm run dev
```

Scaffold with:

```bash
npx create-next-app@latest . --ts --tailwind --app --eslint
npx shadcn@latest init
npx shadcn@latest add card table badge button dialog sonner
```

The backend base URL is read from `NEXT_PUBLIC_API_URL` (default
`http://localhost:8000`).

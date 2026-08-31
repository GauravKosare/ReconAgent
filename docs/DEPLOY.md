# Deploying ReconAgent (₹0)

Two free services: **Vercel** for the Next.js dashboard, **Render** (or a
Hugging Face Docker Space) for the FastAPI backend. MongoDB Atlas M0 is already
provisioned.

```
  Browser ──▶ Vercel (frontend)  ──▶  Render / HF Space (backend)  ──▶  Atlas M0
                NEXT_PUBLIC_API_URL         MONGODB_URI + LLM keys
```

The dashboard falls back to bundled demo data whenever the backend is
unreachable, so the site is never broken while the free dyno is cold.

---

## 1. MongoDB Atlas — allow the backend in

Render and HF free tiers do **not** give a static egress IP, so:

1. Atlas → **Network Access** → **Add IP Address** → `0.0.0.0/0` (allow from
   anywhere). Access is still gated by the SCRAM user + password in the URI.
2. Confirm the app user `reconagent_app` still exists under **Database Access**.

Grab the connection string (**Connect → Drivers**):
`mongodb+srv://reconagent_app:<pw>@reconagent.xxxx.mongodb.net/?retryWrites=true&w=majority`

---

## 2. Backend → Render

**Option A — Blueprint (uses [`render.yaml`](../render.yaml)):**

1. [dashboard.render.com](https://dashboard.render.com) → **New → Blueprint** →
   connect this repo.
2. Render reads `render.yaml` and creates the `reconagent-api` web service
   (Docker, repo-root `Dockerfile`, free plan, health check `/health`).
3. Fill the prompted secrets:
   | Var | Value |
   | --- | --- |
   | `MONGODB_URI` | the Atlas string from step 1 |
   | `GEMINI_API_KEY` / `GROQ_API_KEY` / `OPENROUTER_API_KEY` | your keys (at least one) |
   | `RECONAGENT_CORS_ORIGINS` | leave blank for now; set to the Vercel URL after step 3 |
4. Deploy. First build ~4 min. Test: `curl https://reconagent-api.onrender.com/health`.

`LLM_PRIMARY` / `LLM_FALLBACKS` default to the verified free chain (see
[`.env.example`](../.env.example)); override them as env vars if needed.

**Option B — Hugging Face Docker Space:** create a Space (SDK: Docker), push
this repo, add the same vars as **Settings → Secrets**. The repo-root
`Dockerfile` listens on `$PORT` (7860 on Spaces).

> Free dynos sleep after ~15 min idle; the first request then takes ~50 s.
> Fine for a demo — the frontend shows demo data until the API answers.

---

## 3. Frontend → Vercel

1. [vercel.com/new](https://vercel.com/new) → import this repo.
2. **Root Directory: `frontend`** (Vercel auto-detects Next.js from there).
3. Environment variable:
   | Var | Value |
   | --- | --- |
   | `NEXT_PUBLIC_API_URL` | `https://reconagent-api.onrender.com` (no trailing slash) |
4. Deploy. You get `https://<project>.vercel.app`.
5. Back on Render, set `RECONAGENT_CORS_ORIGINS` to that exact URL and redeploy
   (or trigger a manual deploy).

---

## 4. Smoke test

```bash
curl https://reconagent-api.onrender.com/health
curl https://reconagent-api.onrender.com/samples | head -c 200
```

Then open the Vercel URL → **New batch** → **Run a sample dataset** → pick one.
A live run persists to Atlas and the dashboard renders the real result. If Atlas
is unreachable the run still returns (`summary.persisted = false`) and the page
falls back to demo data.

---

## Redeploys

Both services auto-deploy on push to `main` (`autoDeploy: true` /
Vercel Git integration). No manual step.

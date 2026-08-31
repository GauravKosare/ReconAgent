# ReconAgent — backend

FastAPI service for autonomous three-way reconciliation and settlement-exception
adjudication. See the [repo README](../README.md) and [`docs/`](../docs) for the
full picture.

## Run locally

```bash
pip install -e .[dev]
uvicorn app.main:app --reload --port 8000
```

Needs a `.env` (see [`../.env.example`](../.env.example)) with `MONGODB_URI` and
at least one LLM key. With no keys the pipeline still runs and routes everything
to the human queue.

## Key env vars

| Var | Purpose |
| --- | --- |
| `MONGODB_URI` | Atlas connection string |
| `GEMINI_API_KEY` / `GROQ_API_KEY` / `OPENROUTER_API_KEY` | LLM failover chain |
| `RECONAGENT_CORS_ORIGINS` | comma-separated allowed origins (default `*`) |
| `RECONAGENT_SAMPLES_DIR` | path to `data/samples/realworld` (set in the Docker image) |

## Tests

```bash
pytest -q
```

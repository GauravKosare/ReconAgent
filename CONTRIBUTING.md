# Contributing

## Dev setup

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -e ".[dev]"
```

## Before a PR

```bash
ruff check .
pytest -q
```

## Conventions

- Deterministic code and LLM code stay separated. Anything touching money is a
  pure function with a unit test.
- New exception types go in `app/models/schemas.py::ExceptionCode` **and**
  `app/agent/taxonomy.py` (with an `ALWAYS_HUMAN` decision).
- Never call an LLM provider SDK directly — go through `app/agent/model_client.py`.
- No secrets in code or tests; use `.env`.
- Every new state transition writes an `audit()` entry.

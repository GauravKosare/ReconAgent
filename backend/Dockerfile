# Backend-only image (build context = backend/). The repo-root Dockerfile is
# preferred for deploys — it also bakes in data/samples/realworld so the
# /samples demo endpoint works. Use this one for a slim API-only container.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e .

COPY app ./app

ENV PYTHONUNBUFFERED=1 API_HOST=0.0.0.0 API_PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]

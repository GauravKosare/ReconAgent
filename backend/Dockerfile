# ReconAgent backend — deploys to Hugging Face Spaces / Render / Fly.io
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY app ./app

ENV API_HOST=0.0.0.0 API_PORT=7860
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]

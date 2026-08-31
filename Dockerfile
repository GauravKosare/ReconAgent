# ReconAgent backend — deploys to Render / Hugging Face Spaces / Fly.io.
# Build context is the REPO ROOT so the committed sample datasets ship in the image.
#   docker build -t reconagent .
#   docker run -p 7860:7860 --env-file .env reconagent
FROM python:3.12-slim

WORKDIR /app

# deps first for layer caching
COPY backend/pyproject.toml backend/README.md ./backend/
RUN pip install --no-cache-dir -e ./backend

COPY backend/app ./backend/app
COPY data/samples/realworld ./data/samples/realworld

ENV PYTHONUNBUFFERED=1 \
    API_HOST=0.0.0.0 \
    API_PORT=7860 \
    RECONAGENT_SAMPLES_DIR=/app/data/samples/realworld \
    PYTHONPATH=/app/backend

EXPOSE 7860
# Render/Spaces inject $PORT; fall back to 7860 locally.
CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-7860}"]

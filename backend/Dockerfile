# Docker image for deploying the IncidentGraph backend as a Hugging Face
# Space (free CPU tier: 2 vCPU / 16 GB RAM — enough for the local
# Qwen3-Embedding-0.6B model). HF Spaces route public traffic to port 7860.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/models \
    SENTENCE_TRANSFORMERS_HOME=/app/models/sentence-transformers

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations

RUN pip install --no-cache-dir .

# Pre-download the embedding model into the image layer so the first
# ingestion does not pay the ~1.2 GB download at request time.
RUN python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('Qwen/Qwen3-Embedding-0.6B'); print('model cached, dimension:', m.get_embedding_dimension())"

EXPOSE 7860

# The schema auto-creates on startup (app lifespan); Alembic remains the
# canonical migration tool. Secrets come from Space environment variables —
# never baked into the image.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]

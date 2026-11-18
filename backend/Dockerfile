# Build context: repo root (see docker-compose.yml), so requirements.txt is shared
# with the local venv at the root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    CONFIG_PATH=/app/config/config.toml

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
# Baked-in default; docker-compose bind-mounts ./config over it for live two-way sync.
COPY config/ /app/config/

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
# Single worker on purpose: Milvus Lite allows one process per database file.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

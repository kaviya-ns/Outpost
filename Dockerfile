FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY connectors ./connectors
COPY scripts ./scripts
COPY mocks ./mocks
COPY catalogue ./catalogue

ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8000
ENV S3_ENABLED=false
ENV MOCK_INTERNAL_URL=http://127.0.0.1:8080

EXPOSE 8000

RUN chmod +x scripts/start_production.sh

# Production: API + in-container mocks (Render/Railway). Override for local docker compose if needed.
CMD ["sh", "scripts/start_production.sh"]

FROM python:3.14-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY backend/pyproject.toml backend/README.md ./
COPY backend/app ./app

RUN python -m venv /opt/aether-venv \
    && /opt/aether-venv/bin/pip install --upgrade pip \
    && /opt/aether-venv/bin/pip install .


FROM python:3.14-slim

WORKDIR /app/backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/aether-venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        fonts-liberation \
        libpq5 \
        libreoffice-writer \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin aether

COPY --from=builder /opt/aether-venv /opt/aether-venv
COPY backend/app /app/backend/app
COPY backend/migrations /app/backend/migrations
COPY backend/scripts /app/backend/scripts
COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/docker-entrypoint.sh /usr/local/bin/aether-entrypoint
COPY frontend /app/frontend

RUN mkdir -p /app/backend/private_storage \
    && chown -R aether:aether /app/backend /app/frontend \
    && chmod 0755 /usr/local/bin/aether-entrypoint

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/aether-entrypoint"]
CMD ["sh", "-c", "alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]

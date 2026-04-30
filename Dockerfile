FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && git config --global http.version HTTP/1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && git config --global http.version HTTP/1.1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

COPY --from=builder /install /usr/local
# Install semgrep for static analysis in containers
RUN pip install --no-cache-dir semgrep

COPY src/ ./src/
COPY sql/ ./sql/
COPY alembic.ini .
COPY alembic/ ./alembic/
# Ensure secret key is available at runtime (consistent encryption)
COPY src/.secret_key /app/.secret_key

# Ensure git config is visible to appuser
RUN cp /root/.gitconfig /app/.gitconfig

RUN mkdir -p /app/repos && chown -R appuser:appuser /app

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

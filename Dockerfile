FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && git config --global http.version HTTP/1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ ./src/
RUN env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
    pip install --upgrade pip setuptools wheel && \
    env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
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

# Ensure git config is visible to appuser
RUN cp /root/.gitconfig /app/.gitconfig

RUN mkdir -p /app/repos && chown -R appuser:appuser /app

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

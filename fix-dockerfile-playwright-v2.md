# Fix: `playwright install chromium --with-deps` fallisce anche nel builder

## Problema

`python:3.13` (builder) è basata su Debian slim-like — mancano le librerie
di sistema per Chromium. `--with-deps` tenta di installarle ma non ci riesce
perché mancano prerequisiti base (`wget`, `ca-certificates`, ecc.).

## Soluzione

Installare le dipendenze di sistema nel builder **prima** di `playwright install`,
poi usare `--with-deps` normalmente.

## File da modificare: `Dockerfile`

### Contenuto completo corretto

```dockerfile
ARG PORT=3000
ARG PROXY_CONTENT=TRUE
ARG SOCKS5
ARG API_URL

FROM python:3.13 AS builder

RUN mkdir -p /app/.web
RUN python -m venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Installa dipendenze di sistema necessarie a playwright --with-deps nel builder
RUN apt-get update -y && apt-get install -y \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Installa Chromium in path fissa dentro /app (copiabile nello stage finale)
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright
RUN playwright install chromium --with-deps

COPY rxconfig.py ./
RUN reflex init

COPY . .

ARG PORT API_URL PROXY_CONTENT SOCKS5
RUN REFLEX_API_URL=${API_URL:-http://localhost:$PORT} reflex export --loglevel debug --frontend-only --no-zip && mv .web/build/client/* /srv/ && rm -rf .web


FROM python:3.13-slim

RUN apt-get update -y && apt-get install -y \
    caddy \
    redis-server \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libwayland-client0 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ARG PORT API_URL
ENV PATH="/app/.venv/bin:$PATH" \
    PORT=$PORT \
    REFLEX_API_URL=${API_URL:-http://localhost:$PORT} \
    REDIS_URL=redis://localhost \
    PYTHONUNBUFFERED=1 \
    PROXY_CONTENT=${PROXY_CONTENT:-TRUE} \
    SOCKS5=${SOCKS5:-""} \
    PLAYWRIGHT_BROWSERS_PATH=/app/.playwright

WORKDIR /app
COPY --from=builder /app /app
COPY --from=builder /srv /srv

STOPSIGNAL SIGKILL
EXPOSE $PORT

CMD caddy start && \
    redis-server --daemonize yes && \
    exec reflex run --env prod --backend-only
```

## Riepilogo fix

| Problema | Fix |
|---|---|
| `--with-deps` fallisce nel builder | Aggiunto `apt-get install wget ca-certificates` prima di `playwright install` |
| Chromium perso tra gli stage | `PLAYWRIGHT_BROWSERS_PATH=/app/.playwright` → copiato con `COPY --from=builder /app /app` |
| Dipendenze Chromium nel finale | Installate manualmente senza commenti inline |
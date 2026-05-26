# Fix: Playwright `chromium --with-deps` fallisce su `python:3.13-slim`

## Problema

```
Failed to install browsers
Error: Installation process exited with code: 100
```

`python:3.13-slim` non ha le librerie di sistema richieste da Chromium.
`--with-deps` tenta di installarle ma fallisce perché mancano prerequisiti base.

## File da modificare: `Dockerfile`

### Stage finale — prima

```dockerfile
FROM python:3.13-slim

RUN apt-get update -y && apt-get install -y caddy redis-server && rm -rf /var/lib/apt/lists/*

RUN pip install playwright==1.52.0 && \
    playwright install chromium --with-deps
```

### Stage finale — dopo

```dockerfile
FROM python:3.13-slim

# Installa Caddy, redis e tutte le dipendenze di sistema per Chromium
RUN apt-get update -y && apt-get install -y \
    caddy \
    redis-server \
    # dipendenze Chromium
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
    wget \
    && rm -rf /var/lib/apt/lists/*

# Installa Playwright e scarica Chromium (senza --with-deps perché le deps sono già installate)
RUN pip install playwright==1.52.0 && \
    playwright install chromium
```

## Riepilogo

| Problema | Fix |
|---|---|
| `--with-deps` fallisce su slim | Installa le dipendenze manualmente con `apt-get` |
| `playwright install chromium --with-deps` | → `playwright install chromium` (deps già presenti) |
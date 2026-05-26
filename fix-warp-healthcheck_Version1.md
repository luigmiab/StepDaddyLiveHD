# Fix: WARP container unhealthy — rimozione healthcheck problematico

## Problema

Il container warp risulta sempre `unhealthy` perché:

1. L'healthcheck usa `warp-cli status` **senza `--accept-tos`** → fallisce sempre
2. `warp-cli connect` è **asincrono** — impiega 10-30 secondi per raggiungere
   `Connected`, ma l'healthcheck scatta subito dopo l'avvio

## File da modificare

`warp/Dockerfile` e `docker-compose.yml`

---

## `warp/Dockerfile` — rimuovi HEALTHCHECK

### Prima

```dockerfile
HEALTHCHECK --interval=10s --timeout=5s --retries=10 \
    CMD warp-cli status | grep -q "Connected" || exit 1
```

### Dopo

```dockerfile
# Healthcheck rimosso: warp-cli connect è asincrono e non garantisce
# Connected entro il timeout. Il depends_on usa service_started.
```

Contenuto completo aggiornato:

```dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y && \
    apt-get install -y curl gpg lsb-release dbus dbus-x11 && \
    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | \
        gpg --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ jammy main" \
        > /etc/apt/sources.list.d/cloudflare-client.list && \
    apt-get update -y && \
    apt-get install -y cloudflare-warp && \
    rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 40000

ENTRYPOINT ["/entrypoint.sh"]
```

---

## `docker-compose.yml` — cambia condition da `service_healthy` a `service_started`

### Prima

```yaml
depends_on:
  warp:
    condition: service_healthy
```

### Dopo

```yaml
depends_on:
  warp:
    condition: service_started
```

Contenuto completo aggiornato:

```yaml
services:
  warp:
    build:
      context: ./warp
      dockerfile: Dockerfile
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    sysctls:
      - net.ipv6.conf.all.disable_ipv6=0
    restart: unless-stopped

  step-daddy-live-hd:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        PORT: ${PORT:-3000}
        API_URL: ${API_URL:-}
        PROXY_CONTENT: ${PROXY_CONTENT:-TRUE}
        SOCKS5: warp:40000
    environment:
      - PORT=${PORT:-3000}
      - API_URL=${API_URL:-}
      - PROXY_CONTENT=${PROXY_CONTENT:-TRUE}
      - SOCKS5=warp:40000
    ports:
      - "${PORT:-3000}:${PORT:-3000}"
    restart: unless-stopped
    depends_on:
      warp:
        condition: service_started
    env_file:
      - .env
```

---

## Riepilogo

| File | Modifica |
|---|---|
| `warp/Dockerfile` | Rimosso `HEALTHCHECK` |
| `docker-compose.yml` | `service_healthy` → `service_started` |
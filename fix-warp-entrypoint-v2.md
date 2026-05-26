# Fix: `warp-cli` — comandi aggiornati per versione recente

## Problema

Il container WARP fallisce con:

```
error: unrecognized subcommand 'register'   → ora è: registration new
error: unrecognized subcommand 'set-mode'   → ora è: mode
dbus connection failed                      → dbus non avviato nel container
```

## File da modificare

`warp/Dockerfile` e `warp/entrypoint.sh`

---

## `warp/Dockerfile` — aggiornato

```dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Installa dipendenze + dbus + Cloudflare WARP
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

# WARP proxy mode usa la porta 40000 di default
EXPOSE 40000

HEALTHCHECK --interval=10s --timeout=5s --retries=10 \
    CMD warp-cli status | grep -q "Connected" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
```

---

## `warp/entrypoint.sh` — aggiornato

```bash
#!/bin/bash
set -e

# Avvia dbus (richiesto da warp-svc)
mkdir -p /run/dbus
dbus-daemon --system --fork || true
sleep 2

# Avvia il demone WARP in background
warp-svc &
sleep 5

# Registra WARP (nuovo comando)
warp-cli --accept-tos registration new || true
sleep 2

# Imposta modalità proxy SOCKS5
warp-cli --accept-tos mode proxy
sleep 1

# Connetti
warp-cli --accept-tos connect
sleep 5

echo "=== WARP STATUS ==="
warp-cli status

echo "=== WARP PROXY PORT ==="
# La porta proxy di default è 40000
warp-cli proxy port || true

# Tieni il container in vita
tail -f /dev/null
```

---

## `docker-compose.yml` — aggiorna la porta SOCKS5

WARP in modalità proxy usa la porta `40000` di default (non `1080`).

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
        condition: service_healthy
    env_file:
      - .env
```

---

## Riepilogo comandi warp-cli cambiati

| Vecchio (non funziona) | Nuovo (corretto) |
|---|---|
| `warp-cli register` | `warp-cli registration new` |
| `warp-cli set-mode proxy` | `warp-cli mode proxy` |
| `warp-cli proxy port 1080` | porta default `40000`, non serve settarla |

## Riepilogo file da aggiornare

| File | Modifica |
|---|---|
| `warp/Dockerfile` | Aggiunto `dbus`, porta `40000` |
| `warp/entrypoint.sh` | Comandi `warp-cli` aggiornati, avvio `dbus` |
| `docker-compose.yml` | Porta SOCKS5 `warp:40000` |
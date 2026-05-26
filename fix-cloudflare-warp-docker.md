# Fix: Geo-blocking IP datacenter — integrazione Cloudflare WARP nel container

## Problema

Il server di deploy (datacenter) ha l'IP bloccato da DLHD (geo-block o block datacenter).
Sul PC funziona solo con **Cloudflare WARP** attivo, che maschera l'IP reale e bypassa il blocco.

La soluzione è installare e avviare **Cloudflare WARP** direttamente nel container Docker,
più aggiungere `impersonate="chrome120"` a `curl_cffi` per bypassare i controlli bot Cloudflare
sul sito DLHD.

---

## Modifica 1 — `Dockerfile`

### Cosa aggiungere

Nello stage finale (`FROM python:3.13-slim`), aggiungere l'installazione di WARP
e modificare il `CMD` per avviarlo prima dell'app.

### Prima

```dockerfile
# Final image with only necessary files
FROM python:3.13-slim

# Install Caddy and redis server inside image
RUN apt-get update -y && apt-get install -y caddy redis-server && rm -rf /var/lib/apt/lists/*
```

### Dopo

```dockerfile
# Final image with only necessary files
FROM python:3.13-slim

# Install Caddy, redis and Cloudflare WARP
RUN apt-get update -y && apt-get install -y caddy redis-server curl gpg lsb-release && \
    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ bookworm main" > /etc/apt/sources.list.d/cloudflare-client.list && \
    apt-get update -y && apt-get install -y cloudflare-warp && \
    rm -rf /var/lib/apt/lists/*
```

### CMD — Prima

```dockerfile
CMD caddy start && \
    redis-server --daemonize yes && \
    exec reflex run --env prod --backend-only
```

### CMD — Dopo

```dockerfile
CMD warp-svc --no-autostart & \
    sleep 3 && \
    warp-cli --accept-tos register && \
    warp-cli --accept-tos connect && \
    sleep 3 && \
    caddy start && \
    redis-server --daemonize yes && \
    exec reflex run --env prod --backend-only
```

> **Nota:** il container necessita di `--cap-add NET_ADMIN` e `--device /dev/net/tun`
> per poter creare l'interfaccia TUN di WARP. Vedi Modifica 2.

---

## Modifica 2 — `docker-compose.yml`

WARP richiede privilegi di rete per creare l'interfaccia TUN.

### Prima

```yaml
services:
  step-daddy-live-hd:
    build:
      ...
    ports:
      - "${PORT:-3000}:${PORT:-3000}"
    restart: unless-stopped
```

### Dopo

```yaml
services:
  step-daddy-live-hd:
    build:
      ...
    ports:
      - "${PORT:-3000}:${PORT:-3000}"
    restart: unless-stopped
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    sysctls:
      - net.ipv6.conf.all.disable_ipv6=0
```

---

## Modifica 3 — `StepDaddyLiveHD/step_daddy.py`

Aggiungere `impersonate="chrome120"` alla `AsyncSession` per bypassare
i controlli bot Cloudflare sul sito DLHD (protezione aggiuntiva indipendente da WARP).

### Prima (righe 22-25)

```python
if socks5 != "":
    self._session = AsyncSession(proxy="socks5://" + socks5)
else:
    self._session = AsyncSession()
```

### Dopo

```python
if socks5 != "":
    self._session = AsyncSession(impersonate="chrome120", proxy="socks5://" + socks5)
else:
    self._session = AsyncSession(impersonate="chrome120")
```

---

## Riepilogo modifiche

| File | Modifica |
|---|---|
| `Dockerfile` | Installazione `cloudflare-warp` nello stage finale |
| `Dockerfile` | `CMD` aggiornato per avviare `warp-svc` e `warp-cli connect` |
| `docker-compose.yml` | Aggiunti `cap_add`, `devices`, `sysctls` per interfaccia TUN |
| `StepDaddyLiveHD/step_daddy.py` | `impersonate="chrome120"` su `AsyncSession` |

## Come verificare che WARP sia attivo

Dopo il deploy, nei log del container dovresti vedere:

```
Success
Connected to Cloudflare WARP
```

Oppure esegui nel container:
```bash
docker exec -it <container_id> warp-cli status
```

Output atteso:
```
Status update: Connected
```
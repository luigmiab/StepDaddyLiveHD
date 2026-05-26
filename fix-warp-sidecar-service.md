# Fix: Cloudflare WARP come servizio separato (sidecar SOCKS5)

## Problema

Il server di deploy ha l'IP bloccato da DLHD (geo-block datacenter).
La soluzione è aggiungere un container **WARP dedicato** che espone un proxy SOCKS5
sulla porta `1080`, usato dall'app tramite la variabile `SOCKS5` già supportata dal codice.

## Struttura da aggiungere al repo

```
warp/
└── Dockerfile
```

---

## File da creare: `warp/Dockerfile`

```dockerfile
FROM ubuntu:22.04

# Installa Cloudflare WARP
RUN apt-get update -y && \
    apt-get install -y curl gpg lsb-release && \
    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | \
        gpg --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ jammy main" \
        > /etc/apt/sources.list.d/cloudflare-client.list && \
    apt-get update -y && \
    apt-get install -y cloudflare-warp && \
    rm -rf /var/lib/apt/lists/*

# Installa dante (SOCKS5 proxy server)
RUN apt-get update -y && apt-get install -y dante-server && rm -rf /var/lib/apt/lists/*

# Configurazione dante: espone SOCKS5 sulla porta 1080
# il traffico viene instradato su CloudflareWARP (interfaccia CloudflareWARP)
RUN echo '\
logoutput: stderr\n\
internal: 0.0.0.0 port = 1080\n\
external: CloudflareWARP\n\
socksmethod: none\n\
clientmethod: none\n\
client pass {\n\
    from: 0.0.0.0/0 to: 0.0.0.0/0\n\
    log: error\n\
}\n\
socks pass {\n\
    from: 0.0.0.0/0 to: 0.0.0.0/0\n\
    log: error\n\
}\n\
' > /etc/danted.conf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 1080

ENTRYPOINT ["/entrypoint.sh"]
```

---

## File da creare: `warp/entrypoint.sh`

```bash
#!/bin/bash
set -e

# Avvia il demone WARP
warp-svc --no-autostart &
sleep 5

# Registra e connetti WARP (solo al primo avvio, ignora errori se già registrato)
warp-cli --accept-tos register || true
warp-cli --accept-tos set-mode proxy
warp-cli --accept-tos proxy port 1080 || true
warp-cli --accept-tos connect
sleep 5

echo "WARP status:"
warp-cli status

# Avvia dante SOCKS5 proxy in foreground
exec danted -f /etc/danted.conf
```

> **Nota:** con `warp-cli set-mode proxy`, WARP espone direttamente un proxy SOCKS5
> sulla porta 1080 **senza bisogno di dante**. In questo caso il `Dockerfile` può essere
> semplificato rimuovendo dante e la sua configurazione. Testare quale modalità funziona
> sul proprio host.

---

## File da modificare: `docker-compose.yml`

### Dopo

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
    ports:
      - "1080:1080"

  step-daddy-live-hd:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        PORT: ${PORT:-3000}
        API_URL: ${API_URL:-}
        PROXY_CONTENT: ${PROXY_CONTENT:-TRUE}
        SOCKS5: warp:1080
    environment:
      - PORT=${PORT:-3000}
      - API_URL=${API_URL:-}
      - PROXY_CONTENT=${PROXY_CONTENT:-TRUE}
      - SOCKS5=warp:1080
    ports:
      - "${PORT:-3000}:${PORT:-3000}"
    restart: unless-stopped
    depends_on:
      - warp
    env_file:
      - .env
```

> **Nota:** `SOCKS5=warp:1080` è hardcodato nel compose perché il container warp
> è sempre presente. La variabile `SOCKS5` nell'`env_file` (`.env`) **non deve essere
> impostata**, altrimenti sovrascrive il valore del compose. Rimuovila dalle env vars
> di Dokploy se presente.

---

## Modifica al codice: `StepDaddyLiveHD/step_daddy.py`

Aggiungere `impersonate="chrome120"` per bypassare i controlli bot Cloudflare
sul sito DLHD, indipendentemente dal WARP.

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

## Riepilogo file

| Azione | File |
|---|---|
| ✅ Creare | `warp/Dockerfile` |
| ✅ Creare | `warp/entrypoint.sh` |
| ✏️ Modificare | `docker-compose.yml` |
| ✏️ Modificare | `StepDaddyLiveHD/step_daddy.py` |

## Come verificare che WARP funzioni

```bash
# Entra nel container warp
docker exec -it <warp_container_id> bash

# Controlla lo stato
warp-cli status
# Output atteso: Status update: Connected

# Verifica che l'IP uscente sia Cloudflare
curl --socks5 localhost:1080 https://cloudflare.com/cdn-cgi/trace | grep ip
```
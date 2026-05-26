# Rollback: rimozione `SOCKS5=warp:40000` — ripristino stato funzionante

## Problema

Dopo l'aggiunta del container WARP, tutta l'app è rotta (anche la lista canali)
perché `SOCKS5=warp:40000` è hardcodato e forza tutto il traffico attraverso
un proxy che non funziona ancora.

**Prima di WARP:** lista canali ✅ streaming ❌
**Dopo WARP:** tutto ❌

---

## File da modificare: `docker-compose.yml`

### Contenuto completo aggiornato

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
        SOCKS5: ${SOCKS5:-}
    environment:
      - PORT=${PORT:-3000}
      - API_URL=${API_URL:-}
      - PROXY_CONTENT=${PROXY_CONTENT:-TRUE}
      - SOCKS5=${SOCKS5:-}
    ports:
      - "${PORT:-3000}:${PORT:-3000}"
    restart: unless-stopped
    env_file:
      - .env
```

### Cosa è cambiato

| Cosa | Prima (rotto) | Dopo (ripristinato) |
|---|---|---|
| `SOCKS5` nel build arg | `warp:40000` hardcodato | `${SOCKS5:-}` da env var |
| `SOCKS5` nell'environment | `warp:40000` hardcodato | `${SOCKS5:-}` da env var |
| `depends_on` warp | presente, bloccante | rimosso |

---

## Variabili in Dokploy dopo il ripristino

| Variabile | Valore |
|---|---|
| `PORT` | `3001` |
| `API_URL` | `http://144.217.80.97:3001` |
| `PROXY_CONTENT` | `TRUE` |
| `SOCKS5` | *(lascia vuota)* |
| `DLHD_BASE_URL` | `https://dlhd.pk` |

---

## Stato atteso dopo il redeploy

- ✅ Lista canali torna a funzionare
- ✅ Container warp gira ma **non interferisce** con l'app
- ❌ Streaming ancora bloccato (geo-block) — da risolvere in un secondo momento

## Prossimo passo per WARP (dopo il ripristino)

Verificare che WARP funzioni isolatamente **prima** di collegarlo all'app:

```bash
# Entra nel container warp
docker exec -it <warp_container_id> bash

# Controlla lo stato
warp-cli --accept-tos status
# Deve rispondere: Status update: Connected

# Testa che il proxy funzioni
curl --socks5 localhost:40000 https://cloudflare.com/cdn-cgi/trace | grep ip
# L'IP deve essere un IP Cloudflare, non il tuo server
```

Solo quando questo funziona, reimpostare `SOCKS5=warp:40000` in Dokploy
**senza toccare il `docker-compose.yml`**.
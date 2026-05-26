# Fix: Variabili d'ambiente senza default value causano crash su Dokploy

## Problema

Al deploy su Dokploy, `docker compose` fallisce con:

```
no port specified: :<empty>
The "PORT" variable is not set. Defaulting to a blank string.
```

Dokploy non inietta le variabili d'ambiente nella shell prima di eseguire `docker compose`, quindi `${PORT}` risulta vuoto e Docker non riesce a mappare le porte.

## File da modificare

`docker-compose.yml`

## Modifica da apportare

Aggiungere valori di default (`:-`) a tutte le variabili nella sintassi `${VAR:-default}`.

### Prima

```yaml
services:
  step-daddy-live-hd:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        PORT: ${PORT}
        API_URL: ${API_URL}
        PROXY_CONTENT: ${PROXY_CONTENT}
        SOCKS5: ${SOCKS5}
    environment:
      - PORT=${PORT}
      - API_URL=${API_URL}
      - PROXY_CONTENT=${PROXY_CONTENT}
      - SOCKS5=${SOCKS5}
    ports:
      - "${PORT}:${PORT}"
    restart: unless-stopped
    env_file:
      - .env
```

### Dopo

```yaml
services:
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

## Spiegazione

| Variabile | Default | Note |
|---|---|---|
| `PORT` | `3000` | Porta esposta dal container |
| `API_URL` | *(vuoto)* | Opzionale, configurabile da env |
| `PROXY_CONTENT` | `TRUE` | Comportamento di default atteso |
| `SOCKS5` | *(vuoto)* | Opzionale, solo se si usa un proxy SOCKS5 |

La sintassi `${VAR:-default}` è standard POSIX: usa il valore della variabile se definita, altrimenti il default. Questo rende il `docker-compose.yml` robusto anche quando le variabili non sono iniettate nell'ambiente shell.
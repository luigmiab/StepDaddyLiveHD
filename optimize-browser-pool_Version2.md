# Ottimizzazione: Browser Pool + Cache m3u8

## Obiettivo

Ridurre il tempo di apertura di un canale da ~3-4 secondi a ~1 secondo,
e risolvere il problema dei canali che falliscono quando un player IPTV
pre-risolve tutti i 900 URL in parallelo all'apertura della playlist.

## Problemi attuali in `StepDaddyLiveHD/step_daddy.py`

### Problema 1 — Cold start browser ad ogni richiesta
Il metodo `stream()` esegue:
```python
async with async_playwright() as p:
    browser = await p.chromium.launch(...)  # ~1-2s ogni volta
    ...
    await browser.close()
```
Ogni richiesta lancia e chiude un browser completo. Il costo di startup
è ~1-2 secondi che si sommano al tempo di intercettazione del m3u8.

### Problema 2 — Debug fetch inutile (righe 106-115)
Questo blocco esiste solo per debug e aggiunge ~300-500ms ad ogni richiesta:
```python
if player_url:
    try:
        player_response = await self._session.get(
            player_url,
            headers=self._headers(referer=stream_page_url),
            impersonate="chrome120"
        )
        print(f"[stream][channel={channel_id}] player HTML:\n{player_response.text[:3000]}")
    except Exception as e:
        print(f"[stream][channel={channel_id}] player HTML fetch error: {e}")
```
Va rimosso completamente.

### Problema 3 — Nessuna cache dei risultati
Se 10 richieste arrivano contemporaneamente per lo stesso canale
(es. player IPTV che fa retry), vengono lanciate 10 istanze Playwright
in parallelo per lo stesso URL. Con 900 canali che vengono pre-risolti
tutti insieme, il server crolla.

---

## Soluzione da implementare

### 1. Browser Pool in `StepDaddyLiveHD/step_daddy.py`

Aggiungere un pool di browser persistenti alla classe `StepDaddy`.
Il pool mantiene `POOL_SIZE` browser sempre aperti (letto da
`config.playwright_pool_size`, default 3).

**Struttura del pool:**
- `_browser_pool`: `asyncio.Queue` che contiene i browser disponibili
- `_playwright`: istanza `async_playwright` persistente
- Metodo `async start()`: inizializza playwright e lancia i browser del pool
- Metodo `async stop()`: chiude tutti i browser e playwright
- Il metodo `stream()` prende un browser dal pool con `await pool.get()`,
  lo usa, poi lo rimette con `pool.put_nowait()` — usando `try/finally`
  per garantire che venga sempre restituito anche in caso di errore

**Gestione errori del browser:**
Se un browser crasha deve essere sostituito con uno nuovo prima
di rimetterlo nel pool:
```python
finally:
    try:
        await browser.contexts()  # lancia eccezione se crashato
        self._browser_pool.put_nowait(browser)
    except Exception:
        new_browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage","--disable-blink-features=AutomationControlled"]
        )
        self._browser_pool.put_nowait(new_browser)
```

### 2. Cache m3u8 in `StepDaddyLiveHD/step_daddy.py`

Aggiungere una cache con TTL di 30 secondi:
- `_stream_cache`: dizionario `{channel_id: (m3u8_data, timestamp)}`
- `_stream_locks`: dizionario `{channel_id: asyncio.Lock()}` per evitare
  richieste duplicate concorrenti sullo stesso canale (cache stampede)

**Pattern da usare all'inizio di `stream()`:**
```python
import time

if channel_id not in self._stream_locks:
    self._stream_locks[channel_id] = asyncio.Lock()

async with self._stream_locks[channel_id]:
    cached = self._stream_cache.get(channel_id)
    if cached and (time.time() - cached[1]) < 30:
        return cached[0]

    # ... tutto il codice esistente di Playwright ...

    self._stream_cache[channel_id] = (m3u8_data, time.time())
    return m3u8_data
```

### 3. Lifecycle in `StepDaddyLiveHD/backend.py`

Il pool deve essere avviato e fermato insieme all'app FastAPI.
Sostituire la creazione di `fastapi_app` con un lifespan:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await step_daddy.start()
    yield
    await step_daddy.stop()

fastapi_app = FastAPI(lifespan=lifespan)
```

### 4. Aggiunta `PLAYWRIGHT_POOL_SIZE` in `rxconfig.py`

```python
playwright_pool_size = int(os.environ.get("PLAYWRIGHT_POOL_SIZE", "3"))
config = rx.Config(
    app_name="StepDaddyLiveHD",
    proxy_content=proxy_content,
    socks5=socks5,
    playwright_pool_size=playwright_pool_size,
    show_built_with_reflex=False,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)
```

### 5. Rimozione log di debug in `step_daddy.py`

Rimuovere anche questo print temporaneo:
```python
print(f"[stream][channel={channel_id}] m3u8 content:\n{m3u8.text[:1000]}")
```

---

## Comportamento atteso dopo il fix

| Scenario | Prima | Dopo |
|---|---|---|
| Prima richiesta a un canale | ~3-4s | ~1-1.5s |
| Richiesta successiva entro 30s | ~3-4s | <10ms (cache) |
| 900 canali pre-risolti in parallelo | server crash | coda ordinata (max 3 paralleli) |
| Log duplicati per stesso canale | presenti | eliminati (lock) |

---

## File da modificare

1. `StepDaddyLiveHD/step_daddy.py` — browser pool + cache + rimozione debug
2. `StepDaddyLiveHD/backend.py` — lifespan FastAPI per start/stop pool
3. `rxconfig.py` — aggiunta `PLAYWRIGHT_POOL_SIZE`

## File da NON modificare

- Qualsiasi file in `pages/` e `components/`
- `StepDaddyLiveHD/StepDaddyLiveHD.py`
- `StepDaddyLiveHD/utils.py`
- `StepDaddyLiveHD/meta.json`
- Docker files
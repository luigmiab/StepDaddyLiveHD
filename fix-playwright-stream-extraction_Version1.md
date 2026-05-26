# Fix: Playwright headless per bypass protezione anti-bot JavaScript

## Problema

Il sito DLHD usa protezione anti-bot lato JavaScript:
- Genera cookie/token dinamici tramite JS al caricamento della pagina
- Le richieste HTTP dirette (anche con `curl_cffi`) non eseguono JS → nessun token → 404
- Il problema non è geo-block né TLS fingerprint ma **mancata esecuzione JS**

## Soluzione

Usare **Playwright** con Chromium headless per:
1. Aprire la pagina stream nel browser headless
2. Lasciare che il JS esegua e generi i cookie/token
3. Intercettare la richiesta al file `.m3u8` direttamente dal browser
4. Restituire l'URL o il contenuto all'app

---

## Modifica 1 — `requirements.txt`

### Dopo

```txt
reflex==0.9.3
curl-cffi==0.13.0
httpx[http2]==0.28.1
python-dateutil==2.9.0
fastapi==0.118.0
playwright==1.52.0
```

---

## Modifica 2 — `Dockerfile` (stage builder + stage finale)

### Nel builder — installa dipendenze Playwright

```dockerfile
# Dopo "RUN pip install -r requirements.txt"
RUN playwright install chromium --with-deps
```

### Nello stage finale — installa runtime Playwright

```dockerfile
# Dopo "RUN apt-get install -y caddy redis-server"
RUN pip install playwright==1.52.0 && \
    playwright install chromium --with-deps
```

---

## Modifica 3 — `StepDaddyLiveHD/step_daddy.py`

Sostituire il metodo `stream()` con una versione che usa Playwright
per aprire la pagina e intercettare la richiesta m3u8.

### Import da aggiungere in cima al file

```python
from playwright.async_api import async_playwright
```

### Metodo `stream()` — prima

```python
async def stream(self, channel_id: str):
    key = "CHANNEL_KEY"
    url = f"{self._base_url}/stream/stream-{channel_id}.php"
    response = await self._session.get(url, headers=self._headers())
    matches = re.compile("iframe src=\"(.*)\" width").findall(response.text)
    if matches:
        source_url = matches[0]
        source_response = await self._session.get(source_url, headers=self._headers(url))
    else:
        raise ValueError("Failed to find source URL for channel")

    channel_key = re.compile(rf"const\s+{re.escape(key)}\s*=\s*\"(.*?)\";").findall(source_response.text)[-1]

    data = decode_bundle(source_response.text)
    auth_ts = data.get("b_ts", "")
    auth_sig = data.get("b_sig", "")
    auth_rnd = data.get("b_rnd", "")
    auth_url = data.get("b_host", "")
    auth_request_url = f"{auth_url}auth.php?channel_id={channel_key}&ts={auth_ts}&rnd={auth_rnd}&sig={auth_sig}"
    auth_response = await self._session.get(auth_request_url, headers=self._headers(source_url))
    if auth_response.status_code != 200:
        raise ValueError("Failed to get auth response")
    key_url = urlparse(source_url)
    key_url = f"{key_url.scheme}://{key_url.netloc}/server_lookup.php?channel_id={channel_key}"
    key_response = await self._session.get(key_url, headers=self._headers(source_url))
    server_key = key_response.json().get("server_key")
    if not server_key:
        raise ValueError("No server key found in response")
    if server_key == "top1/cdn":
        server_url = f"https://top1.newkso.ru/top1/cdn/{channel_key}/mono.m3u8"
    else:
        server_url = f"https://{server_key}new.newkso.ru/{server_key}/{channel_key}/mono.m3u8"
    m3u8 = await self._session.get(server_url, headers=self._headers(quote(str(source_url))))
    m3u8_data = ""
    for line in m3u8.text.split("\n"):
        if line.startswith("#EXT-X-KEY:"):
            original_url = re.search(r'URI="(.*?)"', line).group(1)
            line = line.replace(original_url, f"{config.api_url}/key/{encrypt(original_url)}/{encrypt(urlparse(source_url).netloc)}")
        elif line.startswith("http") and config.proxy_content:
            line = f"{config.api_url}/content/{encrypt(line)}"
        m3u8_data += line + "\n"
    return m3u8_data
```

### Metodo `stream()` — dopo

```python
async def stream(self, channel_id: str):
    stream_page_url = f"{self._base_url}/stream/stream-{channel_id}.php"
    m3u8_url = None
    source_url = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Intercetta tutte le richieste di rete
        async def handle_request(request):
            nonlocal m3u8_url, source_url
            url = request.url
            if "mono.m3u8" in url or (url.endswith(".m3u8") and "newkso" in url):
                m3u8_url = url
                # Ricava il source_url dal referer della richiesta
                referer = request.headers.get("referer", "")
                if referer:
                    source_url = referer

        page.on("request", handle_request)

        # Apri la pagina stream — il JS si esegue e genera i token
        await page.goto(stream_page_url, wait_until="networkidle", timeout=30000)

        # Aspetta fino a 15 secondi che il m3u8 venga intercettato
        for _ in range(30):
            if m3u8_url:
                break
            await page.wait_for_timeout(500)

        await browser.close()

    if not m3u8_url:
        raise ValueError(f"Failed to intercept m3u8 URL for channel {channel_id}")

    if not source_url:
        source_url = stream_page_url

    # Scarica il contenuto m3u8 intercettato
    m3u8 = await self._session.get(
        m3u8_url,
        headers=self._headers(referer=source_url),
        impersonate="chrome120"
    )

    m3u8_data = ""
    for line in m3u8.text.split("\n"):
        if line.startswith("#EXT-X-KEY:"):
            original_url = re.search(r'URI="(.*?)"', line).group(1)
            line = line.replace(
                original_url,
                f"{config.api_url}/key/{encrypt(original_url)}/{encrypt(urlparse(source_url).netloc)}"
            )
        elif line.startswith("http") and config.proxy_content:
            line = f"{config.api_url}/content/{encrypt(line)}"
        m3u8_data += line + "\n"

    return m3u8_data
```

---

## Come funziona

```
Richiesta /stream/857.m3u8
        ↓
Playwright apre stream-857.php in Chromium headless
        ↓
JS esegue → genera cookie/token → carica player
        ↓
Playwright intercetta la richiesta al file mono.m3u8 reale
        ↓
curl_cffi scarica il contenuto m3u8 con l'URL intercettato
        ↓
App riscrive gli URL → restituisce m3u8 al client ✅
```

---

## Note importanti

| Aspetto | Dettaglio |
|---|---|
| **Tempo risposta** | Prima richiesta ~5-10 secondi (Chromium avvio) |
| **RAM aggiuntiva** | ~200-300MB per istanza Chromium |
| **Concorrenza** | Ogni richiesta stream apre un browser — considerare un pool se necessario |
| **`--no-sandbox`** | Obbligatorio in Docker, non abbassare la sicurezza in produzione normale |
| **WARP** | Può ancora essere usato come proxy per Playwright aggiungendo `proxy={"server": "socks5://warp:40000"}` al `browser.new_context()` se necessario |

## Riepilogo file da modificare

| File | Modifica |
|---|---|
| `requirements.txt` | Aggiunta `playwright==1.52.0` |
| `Dockerfile` | `playwright install chromium --with-deps` in entrambi gli stage |
| `StepDaddyLiveHD/step_daddy.py` | `import` Playwright + metodo `stream()` riscritto |
# Ottimizzazione velocità stream: Playwright diretto sulla player page

## Contesto

Il flusso attuale in `step_daddy.py → stream()` ha due fasi:
1. `curl_cffi` → `dlhd.pk/stream/stream-{id}.php` → estrae `player_url` dall'iframe
2. `Playwright` → apre `dlhd.pk/stream/stream-{id}.php` con `wait_until="networkidle"` → aspetta il m3u8

**Problema**: Playwright apre la wrapper page da capo, aspetta `networkidle`
(che aspetta che TUTTE le decine di richieste tracking finiscano), e solo
dopo il m3u8 viene intercettato.

**Evidenza dai log**: il m3u8 viene trovato in ~850ms dall'apertura
della **player page**. Ma il tempo totale è molto più lungo perché
Playwright aspetta networkidle sulla wrapper page piena di ads/tracking.

## Obiettivo

Modificare `stream()` in `StepDaddyLiveHD/step_daddy.py` per:

1. Mantenere curl_cffi per estrarre `player_url` dall'iframe (già funziona)
2. Far aprire Playwright **direttamente sulla player page** invece della wrapper
3. Usare `wait_until="commit"` invece di `"networkidle"`
4. Bloccare tutte le richieste non essenziali (tracking, ads, analytics)
5. Chiudere il browser non appena il m3u8 viene trovato (senza aspettare altro)

## Implementazione

Sostituire il metodo `stream()` in `StepDaddyLiveHD/step_daddy.py`
con questa versione ottimizzata:

```python
# Domini da bloccare — tracking, ads, analytics, tutto ciò che non è il player
BLOCKED_DOMAINS = [
    "sharethis.com", "dtscout.com", "dtscdn.com", "tynt.com",
    "lijit.com", "pxdrop.lijit.com", "33across.com", "histats.com",
    "adexchangerapid.com", "whos.amung.us", "adsco.re", "xadsmart.com",
    "doubleclick.net", "googlesyndication.com", "googletagmanager.com",
    "facebook.net", "amazon-adsystem.com",
]

async def stream(self, channel_id: str):
    stream_page_url = f"{self._base_url}/stream/stream-{channel_id}.php"

    # Step 1: curl_cffi → trova player_url dall'iframe (veloce, ~200ms)
    player_url = None
    try:
        response = await self._session.get(
            stream_page_url,
            headers=self._headers(referer=self._base_url),
            impersonate="chrome120"
        )
        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', response.text, re.IGNORECASE)
        if iframe_match:
            player_url = iframe_match.group(1)
            if player_url.startswith("//"):
                player_url = "https:" + player_url
            print(f"[stream][channel={channel_id}] Found player iframe: {player_url}")
    except Exception as e:
        print(f"[stream][channel={channel_id}] curl_cffi error finding iframe: {e}")

    if not player_url:
        raise ValueError(f"Could not find player iframe for channel {channel_id}")

    # Step 2: Playwright → apre DIRETTAMENTE la player page, blocca tracking
    m3u8_url = None
    source_url = player_url

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Blocca tutto il tracking/ads per velocizzare
        async def block_or_continue(route):
            url = route.request.url
            if any(domain in url for domain in BLOCKED_DOMAINS):
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", block_or_continue)

        # Intercetta il m3u8
        async def handle_request(request):
            nonlocal m3u8_url
            url = request.url
            if ".m3u8" in url and ("md5" in url or "mono" in url):
                m3u8_url = url
                print(f"[playwright][channel={channel_id}] ✅ Found m3u8: {url}")

        page.on("request", handle_request)

        # Apri DIRETTAMENTE la player page con referer corretto
        await page.goto(
            player_url,
            wait_until="commit",      # non aspettare networkidle
            timeout=15000,
            referer=stream_page_url   # imposta il referer corretto
        )

        # Aspetta il m3u8 — massimo 8 secondi
        for _ in range(80):
            if m3u8_url:
                break
            await page.wait_for_timeout(100)

        await browser.close()

    if not m3u8_url:
        raise ValueError(f"Failed to intercept m3u8 URL for channel {channel_id}")

    # Step 3: scarica e trasforma il contenuto m3u8 (invariato)
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

## Modifiche chiave rispetto al codice attuale

| Aspetto | Prima | Dopo |
|---|---|---|
| Pagina aperta da Playwright | `dlhd.pk/stream/stream-{id}.php` | `donis.jimpenopisonline.online/premiumtv/daddy2.php?id={id}` |
| `wait_until` | `"networkidle"` | `"commit"` |
| Tracking/ads | tutti caricati | bloccati prima della connessione |
| Polling m3u8 | ogni 500ms | ogni 100ms |
| Timeout polling | 15s | 8s |

## Risultato atteso

- **Prima**: ~5-8 secondi totali (Playwright apre wrapper, aspetta networkidle, tutto il tracking carica)
- **Dopo**: ~1-2 secondi totali (Playwright apre solo player, blocca tracking, trova m3u8 in ~850ms)

## Note importanti

- La costante `BLOCKED_DOMAINS` va definita a livello di modulo (fuori dalla classe)
- La lista dei domini bloccati è ricavata dai log reali delle richieste intercettate
- Il `referer` passato a `page.goto()` è fondamentale: la player page controlla che
  il referer sia `dlhd.pk/stream/stream-{id}.php`, altrimenti potrebbe non caricare il token
- Non toccare nulla di `key()`, `content_url()`, `playlist()`, `load_channels()`
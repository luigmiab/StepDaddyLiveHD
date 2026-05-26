# Fix: Playwright non intercetta m3u8 — pattern allargato + logging + click play

## Problema

```json
{"error": "Failed to intercept m3u8 URL for channel 710"}
```

Playwright apre la pagina ma non intercetta mai il file `.m3u8` perché:
1. Il pattern di intercettazione era troppo stretto (`mono.m3u8` e `newkso`)
2. Il player richiede un click sul pulsante play prima di caricare lo stream
3. `wait_until="networkidle"` aspetta troppo e va in timeout prima che il player parta
4. Nessun logging → impossibile capire cosa sta succedendo

## File da modificare: `StepDaddyLiveHD/step_daddy.py`

### Metodo `stream()` — contenuto completo

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

        # Intercetta TUTTE le richieste — logga tutto per debug
        async def handle_request(request):
            nonlocal m3u8_url, source_url
            url = request.url
            # Log ogni richiesta che contiene parole chiave stream
            if any(ext in url for ext in [".m3u8", ".ts", "stream", "playlist", "manifest"]):
                print(f"[playwright][channel={channel_id}] Intercepted: {url}")
            # Pattern allargato: qualsiasi .m3u8 che non sia la pagina stessa
            if url.endswith(".m3u8") and stream_page_url not in url:
                print(f"[playwright][channel={channel_id}] ✅ Found m3u8: {url}")
                m3u8_url = url
                referer = request.headers.get("referer", "")
                if referer:
                    source_url = referer

        page.on("request", handle_request)

        print(f"[playwright][channel={channel_id}] Opening: {stream_page_url}")
        try:
            # domcontentloaded è più veloce di networkidle
            await page.goto(stream_page_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"[playwright][channel={channel_id}] goto error: {e}")

        # Aspetta che la pagina si stabilizzi
        await page.wait_for_timeout(3000)

        # Prova a cliccare il play button se esiste
        for selector in [
            "button.play",
            ".play-button",
            ".vjs-play-button",
            ".jw-icon-playback",
            "video",
            ".jwplayer",
            "[class*='play']",
            "iframe"
        ]:
            try:
                element = await page.query_selector(selector)
                if element:
                    print(f"[playwright][channel={channel_id}] Clicking: {selector}")
                    await element.click()
                    await page.wait_for_timeout(1000)
                    break
            except Exception:
                pass

        # Aspetta fino a 30 secondi che il m3u8 venga intercettato
        for i in range(60):
            if m3u8_url:
                break
            await page.wait_for_timeout(500)
            if i % 10 == 0:
                print(f"[playwright][channel={channel_id}] Waiting... {i/2}s")

        # Se ancora non trovato, logga il contenuto della pagina
        if not m3u8_url:
            try:
                content = await page.content()
                print(f"[playwright][channel={channel_id}] Page snippet: {content[:1000]}")
            except Exception:
                pass

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

## Cosa cambia rispetto a prima

| Aspetto | Prima | Dopo |
|---|---|---|
| Pattern intercettazione | solo `mono.m3u8` e `newkso` | qualsiasi `.m3u8` non uguale alla pagina |
| `wait_until` | `networkidle` (lento, va in timeout) | `domcontentloaded` (veloce) |
| Click play | assente | prova 8 selettori comuni |
| Timeout attesa m3u8 | 15s | 30s |
| Logging | assente | ogni richiesta stream loggata |
| Fallback debug | assente | stampa HTML pagina se m3u8 non trovato |

## Dopo il redeploy

Fai una richiesta a un canale e controlla i log del container:

```bash
# Dokploy → logs container step-daddy-live-hd
# oppure
docker logs <container_id> -f
```

Nei log vedrai esattamente quale URL viene intercettato

# Fix: dlhd.pk rileva HeadlessChrome e non carica il player

## Problema

Nei log si vede:
```
chua=Chromium%3Bv%3D136%2C%20HeadlessChrome%3Bv%3D136%2C%20Not.A%2FBrand%3Bv%3D99
```

Il sito riceve `HeadlessChrome` nell'header `Sec-Ch-Ua` e serve
una pagina senza player (solo ads). Playwright in modalità headless
espone automaticamente questo header.

## Fix 1 — `requirements.txt`: aggiungi `playwright-stealth`

```txt
reflex==0.9.3
curl-cffi==0.13.0
httpx[http2]==0.28.1
python-dateutil==2.9.0
fastapi==0.118.0
playwright==1.52.0
playwright-stealth==1.0.6
```

## Fix 2 — `StepDaddyLiveHD/step_daddy.py`: applica stealth + patch headers

### Import da aggiungere

```python
from playwright_stealth import stealth_async
```

### Metodo `stream()` — contenuto completo

```python
async def stream(self, channel_id: str):
    stream_page_url = f"{self._base_url}/stream/stream-{channel_id}.php"
    m3u8_url = None
    source_url = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                # Nasconde headless mode
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            # Sovrascrive Sec-Ch-Ua senza HeadlessChrome
            extra_http_headers={
                "Sec-Ch-Ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            }
        )
        page = await context.new_page()

        # Applica stealth per nascondere navigator.webdriver e altri segnali
        await stealth_async(page)

        async def handle_request(request):
            nonlocal m3u8_url, source_url
            url = request.url
            if any(ext in url for ext in [".m3u8", ".ts", "stream", "playlist", "manifest"]):
                print(f"[playwright][channel={channel_id}] Intercepted: {url}")
            if url.endswith(".m3u8") and stream_page_url not in url:
                print(f"[playwright][channel={channel_id}] ✅ Found m3u8: {url}")
                m3u8_url = url
                referer = request.headers.get("referer", "")
                if referer:
                    source_url = referer

        page.on("request", handle_request)

        print(f"[playwright][channel={channel_id}] Opening: {stream_page_url}")
        try:
            await page.goto(stream_page_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"[playwright][channel={channel_id}] goto error: {e}")

        await page.wait_for_timeout(3000)

        # Click play se necessario
        for selector in [
            ".vjs-play-button",
            ".jw-icon-playback",
            "video",
            ".jwplayer",
            "[class*='play']",
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

        # Aspetta fino a 30 secondi
        for i in range(60):
            if m3u8_url:
                break
            await page.wait_for_timeout(500)

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

## Riepilogo fix

| Problema | Fix |
|---|---|
| `HeadlessChrome` in `Sec-Ch-Ua` | Sovrascritto con `extra_http_headers` nel context |
| `navigator.webdriver = true` | `stealth_async(page)` lo nasconde |
| Platform `Linux` sospetta | Cambiato in `Windows` (più comune nei browser reali) |
| `--disable-blink-features=AutomationControlled` | Rimuove flag automazione da Chromium |
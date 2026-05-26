# Fix: HeadlessChrome ancora visibile — sovrascrivere Sec-Ch-Ua via CDP

## Problema

`extra_http_headers` non funziona per `Sec-Ch-Ua` perché Chromium lo
imposta a livello di network stack **prima** che i nostri header vengano
applicati. Il sito vede ancora `HeadlessChrome` e non carica il player.

```
chua=Chromium%3Bv%3D136%2C%20HeadlessChrome%3Bv%3D136%2C%20Not.A%2FBrand%3Bv%3D99
```

## Soluzione

Usare una sessione **CDP** (`Emulation.setUserAgentOverride`) con
`userAgentMetadata` — l'unico modo per sovrascrivere `Sec-Ch-Ua`
a livello di network stack in Chromium.

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
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        # Sovrascrive Sec-Ch-Ua a livello CDP — unico modo per rimuovere HeadlessChrome
        client = await context.new_cdp_session(page)
        await client.send("Emulation.setUserAgentOverride", {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "userAgentMetadata": {
                "brands": [
                    {"brand": "Chromium", "version": "136"},
                    {"brand": "Google Chrome", "version": "136"},
                    {"brand": "Not.A/Brand", "version": "99"},
                ],
                "fullVersionList": [
                    {"brand": "Chromium", "version": "136.0.7103.25"},
                    {"brand": "Google Chrome", "version": "136.0.7103.25"},
                    {"brand": "Not.A/Brand", "version": "99.0.0.0"},
                ],
                "fullVersion": "136.0.7103.25",
                "platform": "Windows",
                "platformVersion": "10.0.0",
                "architecture": "x86",
                "model": "",
                "mobile": False,
            }
        })

        # Stealth manuale — nasconde navigator.webdriver
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

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

        for i in range(60):
            if m3u8_url:
                break
            await page.wait_for_timeout(500)
            if i % 10 == 0:
                print(f"[playwright][channel={channel_id}] Waiting... {i/2}s")

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
| `extra_http_headers` non sovrascrive `Sec-Ch-Ua` | Sostituito con `Emulation.setUserAgentOverride` via CDP |
| `HeadlessChrome` visibile nel network stack | `userAgentMetadata` senza `HeadlessChrome` inviato a livello Chromium |
| `navigator.webdriver` rilevabile | `add_init_script` lo nasconde a livello JS |

## Nei log dopo il fix dovresti vedere

```
chua=Chromium%3Bv%3D136%2C%20Google%20Chrome%3Bv%3D136%2C%20Not.A%2FBrand%3Bv%3D99
```
Senza `HeadlessChrome` — e il player dovrebbe caricarsi.
# Fix: Approccio ibrido — curl_cffi estrae iframe, Playwright apre solo il player

## Problema

Il page snippet non contiene mai il player iframe:
```html
<html><link rel="prefetch" href="https://c.adsco.re/">...
<!-- solo ads e tracking, nessun player -->
```

Il player viene iniettato dal JS solo dopo aver superato check anti-bot
(canvas fingerprint, WebGL, IP reputation) che Playwright non passa
sulla pagina wrapper `dlhd.pk/stream/stream-XXX.php`.

## Soluzione

1. `curl_cffi` scarica `dlhd.pk/stream/stream-XXX.php` (nessun JS, nessun check)
2. Regex estrae `iframe src` → URL del player reale
3. Playwright apre **solo il player** → intercetta m3u8

## File da modificare: `StepDaddyLiveHD/step_daddy.py`

### Metodo `stream()` — contenuto completo

```python
async def stream(self, channel_id: str):
    stream_page_url = f"{self._base_url}/stream/stream-{channel_id}.php"
    m3u8_url = None
    source_url = None

    # Step 1: curl_cffi scarica la pagina wrapper ed estrae l'iframe src
    player_url = None
    try:
        response = await self._session.get(
            stream_page_url,
            headers=self._headers(referer=self._base_url),
            impersonate="chrome120"
        )
        # Cerca iframe src nella pagina
        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', response.text, re.IGNORECASE)
        if iframe_match:
            player_url = iframe_match.group(1)
            if player_url.startswith("//"):
                player_url = "https:" + player_url
            print(f"[stream][channel={channel_id}] Found player iframe: {player_url}")
        else:
            print(f"[stream][channel={channel_id}] No iframe found, falling back to stream page")
            print(f"[stream][channel={channel_id}] Page snippet: {response.text[:500]}")
    except Exception as e:
        print(f"[stream][channel={channel_id}] curl_cffi error: {e}")

    # Fallback: se non trova iframe, usa la pagina stream direttamente
    target_url = player_url or stream_page_url

    # Step 2: Playwright apre solo il player (molto più leggero)
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

        # Sovrascrive Sec-Ch-Ua via CDP
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

        # Stealth manuale
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

        print(f"[playwright][channel={channel_id}] Opening player: {target_url}")
        try:
            await page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=30000,
                referer=stream_page_url  # il player si aspetta il referer della pagina madre
            )
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
                print(f"[playwright][channel={channel_id}] Page snippet: {content[:500]}")
            except Exception:
                pass

        await browser.close()

    if not m3u8_url:
        raise ValueError(f"Failed to intercept m3u8 URL for channel {channel_id}")

    if not source_url:
        source_url = target_url

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

## Flusso dopo il fix

```
curl_cffi → dlhd.pk/stream/stream-868.php
              ↓ estrae iframe src
         → https://wcpkckormoghp.website/player/868
              ↓ Playwright apre solo il player (leggero, nessun check wrapper)
         → intercetta mono.m3u8 ✅
```

## Cosa cercare nei log dopo il redeploy

```
[stream][channel=868] Found player iframe: https://wcpkckormoghp.website/player/868
[playwright][channel=868] Opening player: https://wcpkckormoghp.website/player/868
[playwright][channel=868] ✅ Found m3u8: https://top1.newkso.ru/.../mono.m3u8
```
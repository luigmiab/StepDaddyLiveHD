# Fix: Rimuovi `playwright-stealth` — stealth manuale via `add_init_script`

## Problema

```
ModuleNotFoundError: No module named 'pkg_resources'
```

`playwright-stealth==1.0.6` usa internamente `pkg_resources` che non è
incluso in Python 3.13. La libreria è vecchia e non mantenuta.

## File 1 — `requirements.txt`

### Prima
```txt
reflex==0.9.3
curl-cffi==0.13.0
httpx[http2]==0.28.1
python-dateutil==2.9.0
fastapi==0.118.0
playwright==1.52.0
playwright-stealth==1.0.6
```

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

## File 2 — `StepDaddyLiveHD/step_daddy.py`

### Rimuovi riga 5
```python
# RIMUOVI questa riga
from playwright_stealth import stealth_async
```

### Rimuovi riga 98
```python
# RIMUOVI questa riga
await stealth_async(page)
```

### Aggiungi stealth manuale dopo `page = await context.new_page()` (riga 95)
```python
page = await context.new_page()

# Stealth manuale — nasconde navigator.webdriver e HeadlessChrome
await page.add_init_script("""
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.chrome = { runtime: {} };
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
""")
```

---

## Contenuto completo `step_daddy.py` dopo il fix

```python
import json
import os
import re
from playwright.async_api import async_playwright
from pydantic import BaseModel
from urllib.parse import quote, urlparse
from curl_cffi import AsyncSession
from typing import List
from .utils import encrypt, decrypt, urlsafe_base64, decode_bundle
from rxconfig import config
import html


class Channel(BaseModel):
    id: str
    name: str
    tags: List[str]
    logo: str | None


class StepDaddy:
    def __init__(self):
        socks5 = config.socks5
        if socks5 != "":
            self._session = AsyncSession(impersonate="chrome120", proxy="socks5://" + socks5)
        else:
            self._session = AsyncSession(impersonate="chrome120")
        self._base_url = os.environ.get("DLHD_BASE_URL", "https://dlhd.dad")
        self.channels = []
        with open("StepDaddyLiveHD/meta.json", "r") as f:
            self._meta = json.load(f)

    def _headers(self, referer: str = None, origin: str = None):
        if referer is None:
            referer = self._base_url
        headers = {
            "Referer": referer,
            "user-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0",
        }
        if origin:
            headers["Origin"] = origin
        return headers

    async def load_channels(self):
        channels = []
        try:
            response = await self._session.get(f"{self._base_url}/24-7-channels.php", headers=self._headers())
            matches = re.findall(
                r'<a class="card"\s+href="/watch\.php\?id=(\d+)"[^>]*>\s*<div class="card__title">(.*?)</div>',
                response.text,
                re.DOTALL
            )
            for channel_id, channel_name in matches:
                channel_name = html.unescape(channel_name.strip()).replace("#", "")
                meta = self._meta.get("18+" if channel_name.startswith("18+") else channel_name, {})
                logo = meta.get("logo", "")
                if logo:
                    logo = f"{config.api_url}/logo/{urlsafe_base64(logo)}"
                channels.append(Channel(id=channel_id, name=channel_name, tags=meta.get("tags", []), logo=logo))
            self.channels = sorted(channels, key=lambda channel: (channel.name.startswith("18"), channel.name))
            print(f"[load_channels] Loaded {len(self.channels)} channels.")
        except Exception as e:
            print(f"[load_channels] Error loading channels: {e}")
            raise

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
                extra_http_headers={
                    "Sec-Ch-Ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                }
            )
            page = await context.new_page()

            # Stealth manuale — nasconde navigator.webdriver e HeadlessChrome
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

    async def key(self, url: str, host: str):
        url = decrypt(url)
        host = decrypt(host)
        response = await self._session.get(url, headers=self._headers(f"{host}/", host), timeout=60)
        if response.status_code != 200:
            raise Exception(f"Failed to get key")
        return response.content

    @staticmethod
    def content_url(path: str):
        return decrypt(path)

    def playlist(self):
        data = "#EXTM3U\n"
        for channel in self.channels:
            entry = f" tvg-logo=\"{channel.logo}\",{channel.name}" if channel.logo else f",{channel.name}"
            data += f"#EXTINF:-1{entry}\n{config.api_url}/stream/{channel.id}.m3u8\n"
        return data

    async def schedule(self):
        response = await self._session.get(f"{self._base_url}/schedule/schedule-generated.php", headers=self._headers())
        return response.json()
```

---

## Riepilogo modifiche

| File | Modifica |
|---|---|
| `requirements.txt` | Rimossa riga `playwright-stealth==1.0.6` |
| `step_daddy.py` | Rimosso `import playwright_stealth` |
| `step_daddy.py` | Rimosso `await stealth_async(page)` |
| `step_daddy.py` | Aggiunto `await page.add_init_script(...)` con patch JS manuale |
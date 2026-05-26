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
            # Aggiorna solo se il fetch è andato a buon fine
            self.channels = sorted(channels, key=lambda channel: (channel.name.startswith("18"), channel.name))
            print(f"[load_channels] Loaded {len(self.channels)} channels.")
        except Exception as e:
            # NON azzera self.channels — mantiene i canali precedenti se disponibili
            print(f"[load_channels] Error loading channels: {e}")
            raise

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

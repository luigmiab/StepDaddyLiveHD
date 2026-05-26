# Fix: canali non caricati — errori silenziosi e WARP non pronto

## Problema

La pagina mostra zero canali senza errori visibili. Cause:

1. `load_channels` usa `finally` invece di `except` — azzera sempre i canali anche in caso di errore
2. `update_channels` cattura `CancelledError` con `continue` invece di `raise` — non ritenta correttamente
3. WARP non è pronto quando l'app fa la prima richiesta — la connessione SOCKS5 fallisce silenziosamente

---

## File da modificare: `StepDaddyLiveHD/step_daddy.py`

### Prima — `load_channels` (righe 43-60)

```python
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
    finally:
        self.channels = sorted(channels, key=lambda channel: (channel.name.startswith("18"), channel.name))
```

### Dopo

```python
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
```

---

## File da modificare: `StepDaddyLiveHD/backend.py`

### Prima — `update_channels` (righe 53-59)

```python
async def update_channels():
    while True:
        try:
            await step_daddy.load_channels()
            await asyncio.sleep(300)
        except asyncio.CancelledError:
            continue
```

### Dopo

```python
async def update_channels():
    while True:
        try:
            await step_daddy.load_channels()
            await asyncio.sleep(300)
        except asyncio.CancelledError:
            raise  # permette al task di terminare correttamente
        except Exception as e:
            print(f"[update_channels] Retrying in 30s after error: {e}")
            await asyncio.sleep(30)  # retry veloce in caso di errore
```

---

## File da modificare: `docker-compose.yml`

Aggiungere un `healthcheck` al container warp e usare `condition: service_healthy`
così l'app aspetta che WARP sia effettivamente connesso prima di partire.

### Prima

```yaml
  warp:
    build:
      context: ./warp
      dockerfile: Dockerfile
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    sysctls:
      - net.ipv6.conf.all.disable_ipv6=0
    restart: unless-stopped

  step-daddy-live-hd:
    ...
    depends_on:
      - warp
```

### Dopo

```yaml
  warp:
    build:
      context: ./warp
      dockerfile: Dockerfile
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    sysctls:
      - net.ipv6.conf.all.disable_ipv6=0
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "warp-cli", "status"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 15s

  step-daddy-live-hd:
    ...
    depends_on:
      warp:
        condition: service_healthy
```

---

## Riepilogo

| File | Bug | Fix |
|---|---|---|
| `step_daddy.py` | `finally` azzera canali anche in caso di errore | Spostato dentro `try`, aggiunto log |
| `backend.py` | `CancelledError` con `continue` blocca retry | `raise` su `CancelledError`, retry 30s su altri errori |
| `docker-compose.yml` | App parte prima che WARP sia connesso | `healthcheck` su warp + `condition: service_healthy` |
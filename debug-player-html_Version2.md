# Debug: verifica se il token m3u8 è nell'HTML del player (senza Playwright)

## Obiettivo

Capire se `kolis.phantemlis.top/premiumXXX/index.m3u8?md5v1=...`
è già presente nell'HTML di `daddy5.php?id=XXX` — in quel caso
Playwright può essere rimosso completamente.

## Modifica da fare: `StepDaddyLiveHD/step_daddy.py`

Nel metodo `stream()`, subito dopo il blocco che trova `player_url`
(riga ~87), aggiungere una richiesta curl_cffi alla player page
e loggare l'HTML:

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
        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', response.text, re.IGNORECASE)
        if iframe_match:
            player_url = iframe_match.group(1)
            if player_url.startswith("//"):
                player_url = "https:" + player_url
            print(f"[stream][channel={channel_id}] Found player iframe: {player_url}")
        else:
            print(f"[stream][channel={channel_id}] No iframe found")
            print(f"[stream][channel={channel_id}] Page snippet: {response.text[:500]}")
    except Exception as e:
        print(f"[stream][channel={channel_id}] curl_cffi error: {e}")

    # ── DEBUG: scarica l'HTML della player page e loggalo ──────────────
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
    # ───────────────────────────────────────────────────────────────────

    # Resto del codice invariato (Playwright) ...
```

## Cosa cercare nel log

### Caso A — token nell'HTML ✅ → Playwright non serve

```
[stream][channel=857] player HTML:
<html>...
var playerSource = "https://kolis.phantemlis.top/premium857/index.m3u8?md5v1=EINw0Z...&expires=...";
...
```
oppure
```html
<source src="https://kolis.phantemlis.top/premium857/index.m3u8?md5v1=...">
```

→ In questo caso si elimina Playwright e si usa un regex sull'HTML.

### Caso B — JS offuscato ❌ → Playwright rimane necessario

```
[stream][channel=857] player HTML:
<script>var _0x1a2b=...eval(...)...</script>
```
→ Il token viene calcolato a runtime dal JS, Playwright è necessario
  ma possiamo velocizzarlo bloccando ads/tracking (~300ms invece di ~900ms).

## Dopo aver mandato il log

In base al risultato, il passo successivo sarà:
- **Caso A**: riscrivere `stream()` usando solo `curl_cffi` + regex → ~200ms
- **Caso B**: ottimizzare Playwright bloccando risorse inutili → ~300ms
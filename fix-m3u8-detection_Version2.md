# Fix: m3u8 non riconosciuto perché URL ha query string

## Problema

Il m3u8 viene intercettato ma il codice non lo riconosce:

```
✅ Intercepted: https://zalis.phantemlis.top/premium868/index.m3u8?md5v1=ZmPdGQ...&expires=1779809518
```

La condizione usa `endswith(".m3u8")` ma l'URL ha query string
`?md5v1=...&expires=...` quindi non finisce mai con `.m3u8`.

## File da modificare: `StepDaddyLiveHD/step_daddy.py`

### Modifica nel metodo `stream()` — funzione `handle_request`

```python
# PRIMA ❌
if url.endswith(".m3u8") and stream_page_url not in url:

# DOPO ✅
if ".m3u8" in url and stream_page_url not in url:
```

### Contesto completo della funzione

```python
async def handle_request(request):
    nonlocal m3u8_url, source_url
    url = request.url
    if any(ext in url for ext in [".m3u8", ".ts", "stream", "playlist", "manifest"]):
        print(f"[playwright][channel={channel_id}] Intercepted: {url}")
    # FIX: usa 'in' invece di 'endswith' per gestire URL con query string
    if ".m3u8" in url and stream_page_url not in url:
        print(f"[playwright][channel={channel_id}] ✅ Found m3u8: {url}")
        m3u8_url = url
        referer = request.headers.get("referer", "")
        if referer:
            source_url = referer
```

---

## Problema bonus: 3 istanze Playwright parallele

Nei log si vede che ogni richiesta a `/stream/868.m3u8` avvia
una **nuova istanza Playwright** in parallelo:

```
14:31:58 Opening player  ← richiesta 1
14:32:18 Opening player  ← richiesta 2 (stesso canale, 20s dopo)
14:32:39 Opening player  ← richiesta 3 (stesso canale, 20s dopo)
```

Questo succede perché il client IPTV ritenta ogni ~20s se non riceve
risposta. Il fix del `endswith` risolve anche questo — la risposta
arriverà entro 2-3 secondi invece di 30+.

---

## Risultato atteso nei log dopo il fix

```
[stream][channel=868] Found player iframe: https://donis.jimpenopisonline.online/premiumtv/daddy5.php?id=868
[playwright][channel=868] Opening player: https://donis.jimpenopisonline.online/premiumtv/daddy5.php?id=868
[playwright][channel=868] Intercepted: https://zalis.phantemlis.top/premium868/index.m3u8?md5v1=...
[playwright][channel=868] ✅ Found m3u8: https://zalis.phantemlis.top/premium868/index.m3u8?md5v1=...
```

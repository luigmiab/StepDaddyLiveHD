# Fix: segmenti m3u8 con URL relativi non vengono proxati

## Diagnosi

Aggiungere un log temporaneo nel metodo `stream()` subito dopo
aver scaricato il m3u8, per vedere cosa contiene esattamente:

```python
m3u8 = await self._session.get(
    m3u8_url,
    headers=self._headers(referer=source_url),
    impersonate="chrome120"
)

# LOG TEMPORANEO — rimuovere dopo diagnosi
print(f"[stream][channel={channel_id}] m3u8 content:\n{m3u8.text[:1000]}")
```

## Fix: gestire URL relativi nel m3u8

Il codice attuale proxata solo righe che iniziano con `http`.
Se il m3u8 ha URL relativi come `seg001.ts` o `/premium868/seg001.ts`
non vengono proxati e il browser li cerca sul dominio sbagliato.

### Sostituzione completa del loop di riscrittura nel metodo `stream()`

```python
# Base URL del m3u8 per risolvere URL relativi
from urllib.parse import urljoin

m3u8_base_url = m3u8_url.split("?")[0].rsplit("/", 1)[0] + "/"

m3u8_data = ""
for line in m3u8.text.split("\n"):
    line = line.strip()
    if line.startswith("#EXT-X-KEY:"):
        original_url = re.search(r'URI="(.*?)"', line).group(1)
        # Risolvi URL relativa se necessario
        if not original_url.startswith("http"):
            original_url_abs = urljoin(m3u8_base_url, original_url)
            line = line.replace(f'URI="{original_url}"', f'URI="{original_url_abs}"')
            original_url = original_url_abs
        line = line.replace(
            original_url,
            f"{config.api_url}/key/{encrypt(original_url)}/{encrypt(urlparse(source_url).netloc)}"
        )
    elif not line.startswith("#") and line != "":
        # Segmento — può essere URL assoluto o relativo
        if not line.startswith("http"):
            line = urljoin(m3u8_base_url, line)
        if config.proxy_content:
            line = f"{config.api_url}/content/{encrypt(line)}"
    m3u8_data += line + "\n"

return m3u8_data
```

## Riepilogo fix

| Caso | Prima | Dopo |
|---|---|---|
| `https://zalis.top/seg001.ts` | ✅ proxato | ✅ proxato |
| `seg001.ts` (relativo) | ❌ non proxato | ✅ risolto + proxato |
| `/premium868/seg001.ts` (assoluto senza host) | ❌ non proxato | ✅ risolto + proxato |
| `#EXT-X-KEY URI` relativo | ❌ non risolto | ✅ risolto + proxato |

## Import da aggiungere in cima al file

```python
from urllib.parse import urljoin, urlparse
```

> Nota: `urlparse` è già importato, aggiungere solo `urljoin`.
# Fix: `dlhd.dad` non raggiungibile — rendere il base URL configurabile via env var

## Problema

L'app crasha a runtime con:

```
curl_cffi.requests.exceptions.DNSError: Failed to perform, curl: (6)
Could not resolve host: dlhd.dad
```

Il dominio `dlhd.dad` hardcodato nella riga 26 di `step_daddy.py` non è più raggiungibile.
Il sito DLHD cambia dominio frequentemente — ogni volta bisognerebbe modificare il codice e
rideploare. La soluzione corretta è rendere il base URL configurabile tramite variabile d'ambiente.

## File da modificare

`StepDaddyLiveHD/step_daddy.py`

## Modifica da apportare

### Prima (riga 26)

```python
self._base_url = "https://dlhd.dad"
```

### Dopo

```python
self._base_url = os.environ.get("DLHD_BASE_URL", "https://dlhd.dad")
```

> **Nota:** `os` è già importabile dalla stdlib, ma verificare che sia già importato in cima al file.
> Se non è presente, aggiungere `import os` tra gli import esistenti.

## Modifica completa del file (sezione `__init__`)

### Prima

```python
import json
import re
import reflex as rx
from urllib.parse import quote, urlparse
from curl_cffi import AsyncSession
from typing import List
from .utils import encrypt, decrypt, urlsafe_base64, decode_bundle
from rxconfig import config
import html

class StepDaddy:
    def __init__(self):
        socks5 = config.socks5
        if socks5 != "":
            self._session = AsyncSession(proxy="socks5://" + socks5)
        else:
            self._session = AsyncSession()
        self._base_url = "https://dlhd.dad"
```

### Dopo

```python
import json
import os
import re
import reflex as rx
from urllib.parse import quote, urlparse
from curl_cffi import AsyncSession
from typing import List
from .utils import encrypt, decrypt, urlsafe_base64, decode_bundle
from rxconfig import config
import html

class StepDaddy:
    def __init__(self):
        socks5 = config.socks5
        if socks5 != "":
            self._session = AsyncSession(proxy="socks5://" + socks5)
        else:
            self._session = AsyncSession()
        self._base_url = os.environ.get("DLHD_BASE_URL", "https://dlhd.dad")
```

## Come usarlo in Dokploy

Nella sezione **Environment Variables** del servizio, aggiungere:

```
DLHD_BASE_URL=https://NUOVO-DOMINIO.xxx
```

Sostituire `NUOVO-DOMINIO.xxx` con il dominio attuale di DLHD.

## Vantaggi

| Situazione | Prima | Dopo |
|---|---|---|
| Dominio cambia | Modifica codice + rebuild + redeploy | Aggiorna solo la env var in Dokploy |
| Nuovo deploy | URL hardcodato, potrebbe essere già morto | Legge sempre da env var |
| Rollback dominio | Impossibile senza toccare il codice | Basta cambiare la variabile |

## Riepilogo modifiche

| File | Modifica |
|---|---|
| `StepDaddyLiveHD/step_daddy.py` | Aggiunta `import os` |
| `StepDaddyLiveHD/step_daddy.py` | Riga 26: `self._base_url = os.environ.get("DLHD_BASE_URL", "https://dlhd.dad")` |
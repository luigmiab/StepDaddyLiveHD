# Fix: `warp/entrypoint.sh` — registrazione vecchia + ToS su connect

## Problema

```
Error: Old registration is still around. Try running: "warp-cli registration delete"
Please accept the WARP Terms of Service by passing the --accept-tos flag.
```

1. Al riavvio del container la registrazione precedente persiste → va cancellata prima
2. Il flag `--accept-tos` mancava sul comando `connect`

## File da modificare

`warp/entrypoint.sh`

## Contenuto aggiornato completo

```bash
#!/bin/bash
set -e

# Avvia dbus (richiesto da warp-svc)
mkdir -p /run/dbus
dbus-daemon --system --fork || true
sleep 2

# Avvia il demone WARP in background
warp-svc &
sleep 5

# Cancella registrazione vecchia se presente (evita "Old registration is still around")
warp-cli --accept-tos registration delete || true
sleep 1

# Registra WARP
warp-cli --accept-tos registration new
sleep 2

# Imposta modalità proxy SOCKS5
warp-cli --accept-tos mode proxy
sleep 1

# Connetti (--accept-tos obbligatorio anche qui)
warp-cli --accept-tos connect
sleep 5

echo "=== WARP STATUS ==="
warp-cli --accept-tos status

# Tieni il container in vita
tail -f /dev/null
```

## Riepilogo fix

| Problema | Fix |
|---|---|
| `Old registration is still around` | Aggiunto `registration delete` prima di `registration new` |
| `Please accept the Terms of Service` | Aggiunto `--accept-tos` al comando `connect` e `status` |
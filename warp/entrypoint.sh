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

# Registra WARP (nuovo comando)
warp-cli --accept-tos registration new
sleep 2

# Imposta modalità proxy SOCKS5
warp-cli --accept-tos mode proxy
sleep 1

# Connetti
warp-cli --accept-tos connect
sleep 5

echo "=== WARP STATUS ==="
warp-cli --accept-tos status

# Tieni il container in vita
tail -f /dev/null
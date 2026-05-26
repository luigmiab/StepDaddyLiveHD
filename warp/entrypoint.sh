#!/bin/bash
set -e

# Avvia dbus (richiesto da warp-svc)
mkdir -p /run/dbus
dbus-daemon --system --fork || true
sleep 2

# Avvia il demone WARP in background
warp-svc &
sleep 5

# Registra WARP (nuovo comando)
warp-cli --accept-tos registration new || true
sleep 2

# Imposta modalità proxy SOCKS5
warp-cli --accept-tos mode proxy
sleep 1

# Connetti
warp-cli --accept-tos connect
sleep 5

echo "=== WARP STATUS ==="
warp-cli status

echo "=== WARP PROXY PORT ==="
# La porta proxy di default è 40000
warp-cli proxy port || true

# Tieni il container in vita
tail -f /dev/null
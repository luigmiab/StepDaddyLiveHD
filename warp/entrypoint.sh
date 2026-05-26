#!/bin/bash
set -e

# Avvia il demone WARP
warp-svc --no-autostart &
sleep 5

# Registra e connetti WARP (solo al primo avvio, ignora errori se già registrato)
warp-cli --accept-tos register || true
warp-cli --accept-tos set-mode proxy
warp-cli --accept-tos proxy port 1080 || true
warp-cli --accept-tos connect
sleep 5

echo "WARP status:"
warp-cli status

# Avvia dante SOCKS5 proxy in foreground
exec danted -f /etc/danted.conf
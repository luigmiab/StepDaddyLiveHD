FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Installa dipendenze + dbus + Cloudflare WARP
RUN apt-get update -y && \
    apt-get install -y curl gpg lsb-release dbus dbus-x11 && \
    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | \
        gpg --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ jammy main" \
        > /etc/apt/sources.list.d/cloudflare-client.list && \
    apt-get update -y && \
    apt-get install -y cloudflare-warp && \
    rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# WARP proxy mode usa la porta 40000 di default
EXPOSE 40000

# Healthcheck rimosso: warp-cli connect è asincrono e non garantisce
# Connected entro il timeout. Il depends_on usa service_started.

ENTRYPOINT ["/entrypoint.sh"]
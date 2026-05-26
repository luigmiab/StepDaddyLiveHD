FROM ubuntu:22.04

# Installa Cloudflare WARP
RUN apt-get update -y && \
    apt-get install -y curl gpg lsb-release && \
    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | \
        gpg --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ jammy main" \
        > /etc/apt/sources.list.d/cloudflare-client.list && \
    apt-get update -y && \
    apt-get install -y cloudflare-warp && \
    rm -rf /var/lib/apt/lists/*

# Installa dante (SOCKS5 proxy server)
RUN apt-get update -y && apt-get install -y dante-server && rm -rf /var/lib/apt/lists/*

# Configurazione dante: espone SOCKS5 sulla porta 1080
# il traffico viene instradato su CloudflareWARP (interfaccia CloudflareWARP)
RUN echo '\
logoutput: stderr\n\
internal: 0.0.0.0 port = 1080\n\
external: CloudflareWARP\n\
socksmethod: none\n\
clientmethod: none\n\
client pass {\n\
    from: 0.0.0.0/0 to: 0.0.0.0/0\n\
    log: error\n\
}\n\
socks pass {\n\
    from: 0.0.0.0/0 to: 0.0.0.0/0\n\
    log: error\n\
}\n\
' > /etc/danted.conf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 1080

ENTRYPOINT ["/entrypoint.sh"]
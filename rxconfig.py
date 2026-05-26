import reflex as rx
import os


proxy_content = os.environ.get("PROXY_CONTENT", "TRUE").upper() == "TRUE"
socks5 = os.environ.get("SOCKS5", "")

print(f"PROXY_CONTENT: {proxy_content}\nSOCKS5: {socks5}")

playwright_pool_size = int(os.environ.get("PLAYWRIGHT_POOL_SIZE", "3"))

config = rx.Config(
    app_name="StepDaddyLiveHD",
    proxy_content=proxy_content,
    socks5=socks5,
    playwright_pool_size=playwright_pool_size,
    show_built_with_reflex=False,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)

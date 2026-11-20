"""Локальные шлюзы с фиксированными адресами назначения."""

import asyncio
from ipaddress import IPv4Address, ip_network
import os


IS_MAIL = os.environ.get("PORTAL_MAIL_RELAY") == "1"
if IS_MAIL:
    address = IPv4Address(os.environ["PORTAL_RELAY_IP"])
    if not any(address in ip_network(block) for block in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")):
        raise ValueError("Почтовый шлюз принимает только внутренний IPv4-адрес RFC 1918.")
    upstream = (str(address), int(os.environ.get("PORTAL_RELAY_PORT", "587")))
    listen_port = 2587
else:
    upstream = ("app", 8080)
    listen_port = 8080


async def forward(source, destination):
    while data := await asyncio.wait_for(source.read(65536), timeout=60):
        destination.write(data)
        await asyncio.wait_for(destination.drain(), timeout=30)
    destination.write_eof()


async def relay(client_reader, client_writer):
    upstream_writer = None
    try:
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(asyncio.open_connection(*upstream), timeout=5)
        except (OSError, TimeoutError):
            if not IS_MAIL:
                client_writer.write(
                    b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"
                )
                await asyncio.wait_for(client_writer.drain(), timeout=3)
            return

        async with asyncio.TaskGroup() as streams:
            streams.create_task(forward(client_reader, upstream_writer))
            streams.create_task(forward(upstream_reader, client_writer))
    except* (OSError, TimeoutError):
        pass
    finally:
        client_writer.close()
        if upstream_writer is not None:
            upstream_writer.close()


async def main():
    server = await asyncio.start_server(relay, "0.0.0.0", listen_port)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())

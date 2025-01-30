from asyncio import get_event_loop, run
import asyncio
from pyproto.client import Client
from pyproto.protocol import Direction, Protocol
from pyproto.server import Server

class ProxyTarget(Protocol):
    direction = Direction.server2client
    
    def __init__(self, proxy, protocol_version=None):
        super().__init__(protocol_version)
        self.proxy = proxy

class Proxy(Server):
    direction = Direction.server2client

    def __init__(self, host, port, protocol_version=None):
        super().__init__(protocol_version)
        self.target_host = host
        self.target_port = port
        self.target_client = None

    def on_connection(self):
        asyncio.create_task(self.connect_to_target())

    async def connect_to_target(self):
        loop = get_event_loop()
        _, self.target_client = await loop.create_connection(lambda: ProxyTarget(self), self.target_host, self.target_port)
    
    def on_packet2me(self, data):
        self.target_client.send(data["name"], data["params"])

    def connection_lost(self, exc):
        if self.target_client:
            self.target_client.transport.close()

async def main():
    loop = get_event_loop()
    host_host = "127.0.0.1"
    host_port = 25566
    target_host = "127.0.0.1"
    target_port = 25565

    server = await loop.create_server(lambda: Proxy(target_host, target_port), host_host, host_port)
    async with server:
        await server.serve_forever()

if __name__=="__main__":
    run(main())
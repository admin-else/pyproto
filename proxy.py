import asyncio
from pyproto.client import Client
from pyproto.server import Server

class ProxyClient(Client):
    

    def on_packet2me(self, data):
        

class Proxy(Server):    
    def __init__(self, target_host, target_port):
        self.target_host = target_host
        self.target_port = target_port
        self.transport = None
        self.client_protocol = None

    async def connect_to_target(self):
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_connection(
            lambda: ProxyClient(self.transport),
            self.target_host,
            self.target_port
        )
        self.client_protocol = protocol

    def on_packet2me(self, data):
        handler = getattr(self, f"packet_c2s_{self.state}_{["name"]}", None)
        if not (handler if handler else self.packet_unhandeled)(data):
            self


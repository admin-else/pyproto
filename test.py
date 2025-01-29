import asyncio
from pyproto.protocol import Protocol

class ProxyProtocol(Protocol):
    def __init__(self, target_host, target_port):
        super().__init__()
        self.target_host = target_host
        self.target_port = target_port
        self.transport = None
        self.target_transport = None

    def on_connection(self):
        asyncio.create_task(self.connect_to_target())

    async def connect_to_target(self):
        try:
            loop = asyncio.get_event_loop()
            target_transport, _ = await loop.create_connection(
                lambda: TargetProtocol(self),
                self.target_host,
                self.target_port
            )
            self.target_transport = target_transport
        except Exception as e:
            print(f"Error connecting to target server: {e}")
            self.transport.close()

    def on_packet2me(self, data):
        print(data)

    def on_connection_lost(self, exc):
        if self.target_transport:
            self.target_transport.close()


class TargetProtocol(Protocol):
    def __init__(self, client_protocol):
        super().__init__()
        self.transport = None
        self.client_protocol = client_protocol

    def on_connection_lost(self, exc):
        print("Disconnected from target server")
        if self.client_protocol.transport:
            self.client_protocol.transport.close()

    def on_packet2me(self, data):
        print(data)

async def main():
    # Configuration for the proxy
    listen_host = '127.0.0.1'
    listen_port = 25566
    target_host = '127.0.0.1'
    target_port = 25565

    loop = asyncio.get_event_loop()
    server = await loop.create_server(
        lambda: ProxyProtocol(target_host, target_port),
        listen_host,
        listen_port
    )
    print(f"Proxy server running on {listen_host}:{listen_port} -> {target_host}:{target_port}")
    async with server:
        await server.serve_forever()

# Run the proxy server
if __name__ == "__main__":
    asyncio.run(main())

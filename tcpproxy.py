from asyncio import Protocol, get_event_loop, run, run_coroutine_threadsafe

class ProxyTarget(Protocol):
    def __init__(self, proxy):
        self.proxy = proxy

    def data_received(self, data):
        print("S2C", data)
        self.proxy.transport.write(data)

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        self.proxy.transport.close()

class Proxy(Protocol):
    def __init__(self, host, port):
        self.target_host = host
        self.target_port = port
        self.target_client = None

    def connection_made(self, transport):
        self.transport = transport
        run_coroutine_threadsafe(self.connect_to_target(), get_event_loop())

    async def connect_to_target(self):
        loop = get_event_loop()
        _, self.target_client = await loop.create_connection(lambda: ProxyTarget(self), self.target_host, self.target_port)
    
    def data_received(self, data):
        print("C2S", data)
        if self.target_client:
            self.target_client.transport.write(data)

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
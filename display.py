import asyncio
from pyproto.client import SpawningClient

class LoggingClient(SpawningClient):
    def on_packet2me(self, packet_name, data):
        print("-> ", packet_name, data)
    def on_packet2remote(self, packet_name, data):
        print("<- ", packet_name, data)
    def on_switch_state(self, old_state, new_state):
        print("-- STATE CHANGE", old_state, "->", new_state)

async def main():
    loop = asyncio.get_running_loop()
    client = LoggingClient()
    await loop.create_connection(lambda: client, "127.0.0.1", 25565)
    await client.disconnected.wait()

if __name__=="__main__":
    asyncio.run(main())
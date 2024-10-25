import asyncio
import base64
import json
import time

from pyproto.client import SpawningClient

class Base64Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode('utf-8')
        return super().default(obj)

class ScrapingClient(SpawningClient):
    data = {}

    def packet_unhadeled(self, packet_name, data):
        self.data[packet_name] = data

    def packet_play_map_chunk(self, _):
        self.data["time"] = time.time()
        self.data["profile"] = self.profile
        self.transport.close()

async def main():
    loop = asyncio.get_running_loop()
    client = ScrapingClient()
    await loop.create_connection(lambda: client, "127.0.0.1", 25565)
    await client.disconnected.wait()
    print(json.dumps(client.data, cls=Base64Encoder))
    
if __name__ == "__main__":
    asyncio.run(main())

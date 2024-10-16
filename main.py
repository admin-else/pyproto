import base64
import asyncio
import json

from pyproto.buffer import Buffer
from pyproto.client import SpawningClient

WORLD_HIGHT = 384
BLOCKS_PER_CHUNK = 16


class BytesEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            # Encode bytes as base64 string
            return base64.b64encode(obj).decode("utf-8")
        return super().default(obj)


class ScrapingClient(SpawningClient):
    data = {}

    def packet_unhadeled(self, packet_name, data):
        self.data[packet_name] = data

    def packet_play_map_chunk(self, data):
        data["profile"] = self.profile
        self.transport.close()


async def main():
    with open("minecraft-data/data/pc/1.20.3/protocol.json", "r") as f:
        proto = json.load(f)
        proto["types"]["mapper"] = "native"  # god I FUCKING HATE PROTODEF

    loop = asyncio.get_running_loop()
    client = ScrapingClient(protocol=proto)
    await loop.create_connection(lambda: client, "127.0.0.1", 25565)
    await client.disconnected.wait()
    print(json.dumps(client.data, cls=BytesEncoder))


if __name__ == "__main__":
    asyncio.run(main())

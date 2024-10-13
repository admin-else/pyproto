import asyncio
import json

from pyproto.buffer import Buffer
from pyproto.client import SpawningClient

WORLD_HIGHT = 384
BLOCKS_PER_CHUNK = 16

class ScrapingClient(SpawningClient):
    def packet_unhadeled(self, packet_name, data):
        #print(f"[{packet_name}]: {data}")
        pass

    

    def packet_play_map_chunk(self, data):
        print(data)
        chunk_data_buff = Buffer(data["chunkData"])
        chunk_x = data["x"]
        chunk_y = data["y"]
        # parse chunk data
        for chunk_y in range(WORLD_HIGHT // BLOCKS_PER_CHUNK):
            non_air_block_count = chunk_data_buff.unpack_i16()
            




async def main():
    with open("pyproto/minecraft-data/data/pc/1.20.3/protocol.json", "r") as f:
        proto = json.load(f)
        proto["types"]["mapper"] = "native"  # god I FUCKING HATE PROTODEF

    loop = asyncio.get_running_loop()
    client = ScrapingClient(protocol=proto)
    with open("test_account.json") as f:
        client.profile = json.load(f)
    await loop.create_connection(lambda: client, "127.0.0.1", 25565)
    await client.disconnected.wait()


if __name__ == "__main__":
    asyncio.run(main())

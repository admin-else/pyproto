import asyncio
import json
import zlib
from buffer import Buffer

class Protocol(asyncio.Protocol):
    compression_threshold = -1
    proto = {}
    state = ""
    cipher = None
    types2server = {}
    types2client = {}

    def __init__(self, proto):
        self.transport = None
        self.proto = proto
        self.loop = asyncio.get_event_loop()
        self.ready2recv = asyncio.Event()

    def switch_state(self, state):
        self.state = state
        self.types2server = self.proto["types"].copy()
        self.types2client = self.proto["types"].copy()
        self.types2server.update(self.proto[state]["toServer"]["types"])
        self.types2client.update(self.proto[state]["toServer"]["types"])

    # callbacks
    def packet_unhadeled(self, packet_name, data):
        pass

    def on_connection():
        pass

    def pack_data(self, data):
        b1 = Buffer(types=self.types2server)
        b1.pack("packet", data)
        b2 = Buffer(types=self.types2server)
        if self.compression_threshold >= 0:
            if len(data) >= self.compression_threshold:
                b2.pack_varint(len(b1)) 
                b2.pack_bytes(zlib.compress(b1.unpack_bytes()))
            else:
                b2.pack_varint(0) 
                b2.pack_bytes(b1.unpack_bytes())
        else:
            b2.pack_bytes(b1.unpack_bytes())

        b3 = Buffer(types=self.types2server)
        b3.pack_varint(len(b2))
        b3.pack_bytes(b2.unpack_bytes())
        return b3.unpack_bytes()

    def send(self, packet_name, data = None):
        self.transport.write(self.pack_data({"name": packet_name, "params": data}))

    def connection_made(self, transport):
        self.transport = transport
        self.on_connection()
        self.ready2recv.set()

    def connection_lost(self, exc):
        print("Connection Lost")
        self.loop.stop()

    async def data_received(self, data):
        await self.ready2recv.wait()
        # TODO: Add encryption
        buff = Buffer(data, types=self.types2client)
        buff = Buffer(buff.unpack_bytes(buff.unpack_varint()))
        # TODO: Add compression
        data = buff.unpack("packet")
        method = getattr(self, f"packet_{data["name"]}")
        if method:
            method(data["params"])
        else:
            self.packet_unhadeled(data["name"], data["params"])

class StatusClient(Protocol):
    def on_connection(self):
        self.switch_state("handshaking")
        self.send("set_protocol", {'protocolVersion': 765, 'serverHost': 'localhost', 'serverPort': 25565, 'nextState': 1})
        self.switch_state("status")
        self.send("ping_start")

    def packet_status_respose(self, data):
        print(data)

async def main():
    with open("minecraft-data/data/pc/1.20.3/protocol.json", "r") as f:
        proto = json.load(f)
        proto["types"]["mapper"] = "native" # god I FUCKING HATE PROTODEF

    loop = asyncio.get_running_loop()
    await loop.create_connection(lambda: StatusClient(proto=proto), "127.0.0.1", 25565)
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())

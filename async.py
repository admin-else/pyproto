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
        self.disconnected = asyncio.Event()
        self.recvbuff = Buffer()

    def switch_state(self, state):
        print("state:",state)
        self.state = state
        self.types2server = self.proto["types"].copy()
        self.types2client = self.proto["types"].copy()
        self.types2server.update(self.proto[state]["toServer"]["types"])
        self.types2client.update(self.proto[state]["toClient"]["types"])

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
        print("->",packet_name)
        self.transport.write(self.pack_data({"name": packet_name, "params": data}))

    def connection_made(self, transport):
        self.transport = transport
        self.on_connection()
        self.ready2recv.set()

    def connection_lost(self, exc):
        print("disconnet", exc)
        self.disconnected.set()

    def data_received(self, data):
        asyncio.create_task(self.handle_data_received(data))

    async def handle_data_received(self, data):
        await self.ready2recv.wait()
        # TODO: Add encryption
        data = Buffer(data)

        if not self.recvbuff.pos:
            self.recvbuff.pos = data.unpack_varint() # this is stupid but i can do it

        self.recvbuff.pack_bytes(data.unpack_bytes(min(len(self.recvbuff)-self.recvbuff.pos,len(data))))

        if len(self.recvbuff) != self.recvbuff.pos:
            return
        
        self.recvbuff.data = self.recvbuff.data[self.recvbuff.pos:]
        
        buff = Buffer(self.recvbuff.data, types=self.types2client)

    def consistent_data(self, buff):
        if self.compression_threshold >= 0:
            uncompressed_length = buff.unpack_varint()
            if uncompressed_length > 0:
                buff = Buffer(zlib.decompress(buff.unpack_bytes()), types=self.types2client)
        data = buff.unpack("packet")

        print("<-",data["name"])

        method = getattr(self, f"packet_{self.state}_{data["name"]}", None)
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

    def packet_status_server_info(self, data):
        self.status = json.loads(data["response"])
        self.transport.close()

class Client(Protocol):
    def on_connection(self):
        self.switch_state("handshaking")
        self.send("set_protocol", {'protocolVersion': 765, 'serverHost': 'localhost', 'serverPort': 25565, 'nextState': 2})
        self.switch_state("login")
        self.send("login_start", {"username": "sigma", "playerUUID": "00000000-0000-0000-0000-000000000000"})

    def packet_unhadeled(self, packet_name, data: dict):
        pass

    def packet_login_compress(self, data):
        self.compression_threshold = data["threshold"]

    def packet_login_success(self, data):
        self.send("login_acknowledged")
        self.switch_state("configuration")

    def packet_finish_configuration(self, data):
        self.send("finish_configuration")
        self.switch_state("play")

async def main():
    with open("minecraft-data/data/pc/1.20.3/protocol.json", "r") as f:
        proto = json.load(f)
        proto["types"]["mapper"] = "native" # god I FUCKING HATE PROTODEF

    loop = asyncio.get_running_loop()
    client = Client(proto=proto)
    
    await loop.create_connection(lambda: client, "127.0.0.1", 25565)
    await client.disconnected.wait()

if __name__ == "__main__":
    asyncio.run(main())

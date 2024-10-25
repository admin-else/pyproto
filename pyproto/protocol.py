import asyncio
from enum import Enum
from cryptography.hazmat.primitives import ciphers
from cryptography.hazmat.primitives.ciphers import algorithms, modes
import zlib
from pyproto.buffer import Buffer
import pyproto.data

DEFAULT_PROTO_VERS = 765 # why no reason

class Direction(Enum):
    client2server = "client2server"
    server2client = "server2client"

class OfflineModeExeption(Exception): ...

class AuthExeption(Exception): ...

class Protocol(asyncio.Protocol):
    compression_threshold = -1
    protocol = {}
    state = ""
    types2remote = {}
    types2me = {}
    direction: Direction
    protocol_version = 765
    encryptor = None
    decryptor = None

    def get_protocol(self, protocol_version=None, version=None):
        if not (protocol_version or version):
            protocol_version = DEFAULT_PROTO_VERS

        if protocol_version:
            data = [version["minecraftVersion"] for version in pyproto.data.common("protocolVersions") if version["version"] == protocol_version]
            if not data:
                raise ValueError(f"Did not find protocol version {protocol_version}.")
            version = data[0]

        return pyproto.data.get(version, "protocol")

    def __init__(self, protocol_version=None, version=None):
        self.transport = None
        self.protocol = self.get_protocol(protocol_version, version)
        self.loop = asyncio.get_event_loop()
        self.ready2recv = asyncio.Event()
        self.disconnected = asyncio.Event()
        self.recvbuff = Buffer()

    def switch_state(self, state):
        self.state = state
        self.types2remote = self.protocol["types"].copy()
        self.types2me = self.protocol["types"].copy()
        me, remote = self.direction.value.split("2")
        self.types2me.update(
            self.protocol[state][f"to{me.title()}"]["types"]
        )  # the .title is for camel case
        self.types2remote.update(self.protocol[state][f"to{remote.title()}"]["types"])

    def enable_encryption(self, shared_secret):
        cipher = ciphers.Cipher(
            algorithms.AES(shared_secret), modes.CFB8(shared_secret)
        )
        self.encryptor = cipher.encryptor()
        self.decryptor = cipher.decryptor()

    def pack_data(self, data):
        b1 = Buffer(types=self.types2remote)
        b1.pack("packet", data)
        b2 = Buffer(types=self.types2remote)
        if self.compression_threshold >= 0:
            if len(data) >= self.compression_threshold:
                b2.pack_varint(len(b1))
                b2.pack_bytes(zlib.compress(b1.unpack_bytes()))
            else:
                b2.pack_varint(0)
                b2.pack_bytes(b1.unpack_bytes())
        else:
            b2.pack_bytes(b1.unpack_bytes())

        b3 = Buffer(types=self.types2remote)
        b3.pack_varint(len(b2))
        b3.pack_bytes(b2.unpack_bytes())
        data = b3.unpack_bytes()
        if self.encryptor is not None:
            data = self.encryptor.update(data)
        return data

    def send(self, packet_name, data=None):
        self.transport.write(self.pack_data({"name": packet_name, "params": data}))

    def connection_made(self, transport):
        self.transport = transport
        self.on_connection()
        self.ready2recv.set()

    def connection_lost(self, exc):
        self.disconnected.set()
        self.on_connection_lost(exc)

    def data_received(self, data):
        asyncio.create_task(
            self.handle_data_received(data)
        )  # needs to be async for the ready2recv flag

    async def handle_data_received(self, data):
        await self.ready2recv.wait()
        if self.decryptor is not None:
            data = self.decryptor.update(data)

        self.recvbuff.pack_bytes(data)

        while True:
            self.recvbuff.save()
            try:
                buff = Buffer(
                    self.recvbuff.unpack_bytes(self.recvbuff.unpack_varint()),
                    self.types2me,
                )
                if self.compression_threshold >= 0:
                    uncompressed_length = buff.unpack_varint()
                    if uncompressed_length > 0:
                        buff = Buffer(
                            zlib.decompress(buff.unpack_bytes()),
                            types=self.types2me,
                        )
                buff.save()
                data = buff.unpack("packet")
            except IndexError:
                self.recvbuff.restore()
                return
            method = getattr(self, f"packet_{self.state}_{data["name"]}", None)
            if method:
                method(data["params"])
            else:
                self.packet_unhadeled(data["name"], data["params"])

    # callbacks
    def packet_unhadeled(self, packet_name, data):
        pass

    def on_connection(self):
        pass

    def on_connection_lost(self, exc):
        pass

    def on_switch_state(self, old_state, new_state):
        pass



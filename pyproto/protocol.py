import asyncio
from enum import Enum

from cryptography.hazmat.primitives import ciphers
from cryptography.hazmat.primitives.ciphers import algorithms, modes
import zlib
from pyproto.buffer import Buffer
import pyproto.data

class Direction(Enum):
    client2server = "client2server"
    server2client = "server2client"

class OfflineModeException(Exception): ...

class AuthException(Exception): ...

class Protocol(asyncio.Protocol):
    compression_threshold = -1
    protocol = {}
    state = "offline"
    types2remote = {}
    types2me = {}
    direction: Direction
    protocol_version = pyproto.data.LATEST_PROTOCOL_VERSION
    encryptor = None
    decrypter = None

    def __init__(self, protocol_version=None):
        self.transport = None
        self.load_protocol(protocol_version)
        self.loop = asyncio.get_event_loop()
        self.ready2recv = asyncio.Event()
        self.disconnected = asyncio.Event()
        self.recv_buff = Buffer()

    def load_protocol(self, protocol_version):
        self.protocol, self.protocol_version, self.version_name = pyproto.data.get_protocol(protocol_version)
        self.protocol["types"]["mapper"] = "native"

    def switch_state(self, state):
        old_state = self.state
        self.state = state
        self.types2remote = self.protocol["types"].copy()
        self.types2me = self.protocol["types"].copy()
        me, remote = self.direction.value.split("2")
        self.types2me.update(
            self.protocol[state][f"to{me.title()}"]["types"]
        )  # the .title is for camel case
        self.types2remote.update(self.protocol[state][f"to{remote.title()}"]["types"])
        self.on_switch_state(old_state, state)

    def enable_encryption(self, shared_secret):
        cipher = ciphers.Cipher(
            algorithms.AES(shared_secret), modes.CFB8(shared_secret)
        )
        self.encryptor = cipher.encryptor()
        self.decrypter = cipher.decryptor()

    def pack_data(self, data):
        b1 = Buffer(types=self.types2remote)
        b1.pack("packet", data)
        return self.pack_bytes(b1.data)

    def pack_bytes(self, data):
        b2 = Buffer(types=self.types2remote)
        if self.compression_threshold >= 0:
            if len(data) >= self.compression_threshold:
                b2.pack_varint(len(data))
                b2.pack_bytes(zlib.compress(data))
            else:
                b2.pack_varint(0)
                b2.pack_bytes(data)
        else:
            b2.pack_bytes(data)

        b3 = Buffer(types=self.types2remote)
        b3.pack_varint(len(b2))
        b3.pack_bytes(b2.unpack_bytes())
        data = b3.unpack_bytes()
        if self.encryptor is not None:
            data = self.encryptor.update(data)
        return data

    def send(self, packet_name, data=None):
        if data is None:
            data = {}
        data = {"name": packet_name, "params": data}
        self.on_packet2remote(data)
        self.transport.write(self.pack_data(data))

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
        if self.decrypter is not None:
            data = self.decrypter.update(data)

        self.recv_buff.pack_bytes(data)

        while True:
            self.recv_buff.save()
            try:
                buff = Buffer(
                    self.recv_buff.unpack_bytes(self.recv_buff.unpack_varint()),
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
            #except Exception as e:
            #    print(e)
            except IndexError:
                self.recv_buff.restore()
                return
            
            self.on_packet2me(data)

    # callbacks
    def on_connection(self):
        pass

    def on_connection_lost(self, exc):
        pass

    def on_switch_state(self, old_state, new_state):
        pass

    def on_packet2remote(self, data):
        pass

    def on_packet2me(self, data):
        pass

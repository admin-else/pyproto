import asyncio
from enum import Enum
import json
import os
from cryptography.hazmat.primitives import serialization, ciphers
from cryptography.hazmat.primitives.ciphers import algorithms, modes
import hashlib
import zlib
from buffer import Buffer
import requests
from cryptography.hazmat.primitives.asymmetric import padding


class Direction(Enum):
    client2server = "client2server"
    server2client = "server2client"


HANSHAKE_STATE_TO_ID = {"play": 2, "status": 1}


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

    def __init__(self, protocol):
        self.transport = None
        self.protocol = protocol
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
        # TODO: Add encryption
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
            print(f"<-{data["nam"]}")
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


class Client(Protocol):
    direction = Direction.client2server
    handshake_server_host = (
        "github.com/admin-else/pyproto"  # can be anything does not really matter
    )
    handshake_server_port = 25565
    next_state: str  # can be play or status

    def on_connection(self):
        self.switch_state("handshaking")
        self.send(
            "set_protocol",
            {
                "protocolVersion": self.protocol_version,
                "serverHost": self.handshake_server_host,
                "serverPort": self.handshake_server_port,
                "nextState": HANSHAKE_STATE_TO_ID[self.next_state],
            },
        )
        self.on_handshake()

    def on_handshake(self):
        pass


class SpawningClient(Client):
    direction = Direction.client2server
    next_state = "play"
    name: str
    uuid: str  # no dashes important
    auth_server = "https://sessionserver.mojang.com/"  # with / at the end
    token: str | None = None  # if none offline mode

    def on_handshake(self):
        self.switch_state("login")
        self.send("login_start", {"username": self.name, "playerUUID": self.uuid})

    def packet_login_encryption_begin(self, data):
        if self.token is None:
            self.transport.close()
            raise OfflineModeExeption("Cannot join online mode server without token.")

        shared_secret = os.urandom(16)
        public_key = serialization.load_der_public_key(data["publicKey"])

        sha1 = hashlib.sha1()
        for contents in (
            data["serverId"].encode("ascii"),
            shared_secret,
            data["publicKey"],
        ):
            sha1.update(contents)

        digest = int(sha1.hexdigest(), 16)
        if digest >> 39 * 4 & 0x8:
            digest = "-%x" % ((-digest) & (2 ** (40 * 4) - 1))
        else:
            digest = "%x" % digest

        r = requests.post(
            self.auth_server + "session/minecraft/join",
            json={
                "accessToken": self.token,
                "selectedProfile": self.uuid,
                "serverID": digest,
            },
        )

        # if not r.ok:
        #    self.transport.close()
        #    raise AuthExeption(f"Join error {r.status_code}: {r.json()}")

        self.enable_encryption(shared_secret)
        self.send(
            "encryption_begin",
            {
                "sharedSecret": public_key.encrypt(
                    plaintext=shared_secret, padding=padding.PKCS1v15()
                ),
                "verifyToken": public_key.encrypt(
                    plaintext=data["verifyToken"], padding=padding.PKCS1v15()
                ),
            },
        )

    def packet_unhadeled(self, packet_name, data: dict):
        print(f"[{self.state}] {packet_name}: {data}")

    def packet_login_compress(self, data):
        self.compression_threshold = data["threshold"]

    def packet_login_success(self, data):
        self.send("login_acknowledged")
        self.switch_state("configuration")

    def packet_configuration_finish_configuration(self, data):
        self.send("finish_configuration")
        self.switch_state("play")

    def packet_play_keep_alive(self, data):
        self.send("keep_alive", data)


async def main():
    with open("minecraft-data/data/pc/1.20.3/protocol.json", "r") as f:
        proto = json.load(f)
        proto["types"]["mapper"] = "native"  # god I FUCKING HATE PROTODEF

    loop = asyncio.get_running_loop()
    client = SpawningClient(protocol=proto)
    client.name = "Admin_Else"
    client.uuid = "3632330d373742708e8f270e581c45db"
    client.token = "eyJraWQiOiJhYzg0YSIsImFsZyI6IkhTMjU2In0.eyJ4dWlkIjoiMjUzNTQwODczNjU4Mzg2NyIsImFnZyI6IkFkdWx0Iiwic3ViIjoiZmFjYWQ2NjYtNGFiYS00MDU3LTlmOWQtMzQ5NDI2NDQ2MzAzIiwiYXV0aCI6IlhCT1giLCJucyI6ImRlZmF1bHQiLCJyb2xlcyI6W10sImlzcyI6ImF1dGhlbnRpY2F0aW9uIiwiZmxhZ3MiOlsidHdvZmFjdG9yYXV0aCIsIm1zYW1pZ3JhdGlvbl9zdGFnZTQiLCJvcmRlcnNfMjAyMiIsIm11bHRpcGxheWVyIl0sInByb2ZpbGVzIjp7Im1jIjoiMzYzMjMzMGQtMzczNy00MjcwLThlOGYtMjcwZTU4MWM0NWRiIn0sInBsYXRmb3JtIjoiVU5LTk9XTiIsInl1aWQiOiJkYWI0ZDRkMmYwNTc0N2FjZjE4OWExZTUxNTAzOWRjZCIsIm5iZiI6MTcyODM0MjA4NiwiZXhwIjoxNzI4NDI4NDg2LCJpYXQiOjE3MjgzNDIwODZ9.mbjq6GklECmg5lK1_aE2u7bJILdqfNBfaEPJGvvdEJY"

    await loop.create_connection(lambda: client, "127.0.0.1", 25565)
    await client.disconnected.wait()


if __name__ == "__main__":
    asyncio.run(main())

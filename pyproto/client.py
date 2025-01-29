import hashlib
import os
import json

import requests
from pyproto.protocol import Protocol, Direction
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization


class OfflineModeExeption(Exception): ...


class AuthExeption(Exception): ...


class Client(Protocol):
    direction = Direction.client2server
    handshake_server_host = (
        "github.com/admin-else/pyproto"  # can be anything does not really matter
    )
    handshake_server_port = 25565
    next_state: int  # can be play or status

    def on_connection(self):
        self.switch_state("handshaking")
        self.send(
            "set_protocol",
            {
                "protocolVersion": self.protocol_version,
                "serverHost": self.handshake_server_host,
                "serverPort": self.handshake_server_port,
                "nextState": self.next_state,
            },
        )
        self.on_handshake()

    def on_handshake(self):
        pass


class StatusClient(Client):
    next_state = 1

    def __init__(self, protocol_version=None, version=None):
        super().__init__(protocol_version, version)
        self.status_data = None

    def on_packet2me(self, packet_name, data):
        method = getattr(self, f"packet_{self.state}_{data["name"]}", None)
        if method:
            method(data["params"])
        else:
            self.packet_unhandled(data["name"], data["params"])

    def packet_unhandled(self, name, data):
        pass

    def on_handshake(self):
        self.switch_state("status")
        self.send("ping_start")

    def packet_status_server_info(self, data):
        self.status_data = json.loads(data["response"])
        self.transport.close()


class SpawningClient(Client):
    next_state = 2
    profile = {}

    def on_handshake(self):
        self.switch_state("login")
        self.send(
            "login_start",
            {
                "username": self.profile.get("name", "pyproto"),
                "playerUUID": self.profile.get(
                    "id", "00000000000000000000000000000000"
                ),
            },
        )

    def packet_login_encryption_begin(self, data):
        if self.profile.get("access_token") is None:
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
            self.profile.get(
                "joinserverapi",
                "https://sessionserver.mojang.com/session/minecraft/join",
            ),
            json={
                "accessToken": self.profile.get("access_token"),
                "selectedProfile": self.profile.get("id"),
                "serverId": digest,
            },
        )

        if not r.ok:
            self.transport.close()
            raise AuthExeption(f"Join error {r.status_code}: {r.json()}")
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
        self.enable_encryption(shared_secret)

    def packet_login_compress(self, data):
        self.compression_threshold = data["threshold"]

    def packet_login_success(self, data):
        self.send("login_acknowledged")
        self.switch_state("configuration")

    def packet_configuration_finish_configuration(self, data):
        self.send("finish_configuration")
        self.switch_state("play")
    
    def packet_configuration_ping(self, data):
        self.send("pong", {"id": data["id"]})

    def packet_play_keep_alive(self, data):
        self.send("keep_alive", data)

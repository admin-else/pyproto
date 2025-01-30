import json
from pyproto.protocol import Direction, Protocol


class Server(Protocol):
    direction = Direction.server2client

    def on_packet2me(self, data):
        method = getattr(self, f"packet_{self.state}_{data["name"]}", None)
        if method is not None:
            method(data["params"])
        else:
            self.packet_unhandeled(data)

    def packet_unhandeled(self, data):
        pass

    def packet_handshaking_set_protocol(self, data):
        if self.protocol_version != data["protocolVersion"]:
            self.load_protocol(data["protocolVersion"])

        if data["nextState"] == 1:
            self.switch_state("status")
        if data["nextState"] == 2:
            self.switch_state("login")


class PingabelServer(Server):
    DESCRIPTION = {"text": "Hello, world!"}

    def get_status(self):
        return {
            "version": {"name": self.version_name, "protocol": self.protocol_version},
            "players": {
                "max": 0,
                "online": 0,
                "sample": [
                ]
            },
            "description": self.DESCRIPTION
        }

    def packet_status_ping_start(self, packet):
        self.send("server_info", {"response": json.dumps(self.get_status())})

    def packet_status_ping(self, data):
        self.send("ping", {"time": data["time"]})
        self.transport.close()

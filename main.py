from buffer import Buffer
import socket
import json
import zlib

with open("minecraft-data/data/pc/1.20.3/protocol.json", "r") as f:
    proto = json.load(f)
    proto["types"]["mapper"] = "native" # god I FUCKING HATE PROTODEF

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
state = "handshaking"
c2s_types = {}
s2c_types = {}
compression_threshold = -1

def update_state(state):
    global c2s_types, s2c_types
    c2s_types = proto["types"].copy()
    s2c_types = proto["types"].copy()
    c2s_types.update(proto[state]["toServer"]["types"])
    s2c_types.update(proto[state]["toClient"]["types"])

def pack_data(data, types):
    b1 = Buffer(types=types)
    b1.pack("packet", data)
    b2 = Buffer(types=types)
    if compression_threshold >= 0:
        if len(data) >= compression_threshold:
            b2.pack_varint(len(b1)) 
            b2.pack_bytes(zlib.compress(b1.unpack_bytes()))
        else:
            b2.pack_varint(0) 
            b2.pack_bytes(b1.unpack_bytes())
    else:
        b2.pack_bytes(b1.unpack_bytes())

    b3 = Buffer(types=types)
    b3.pack_varint(len(b2))
    b3.pack_bytes(b2.unpack_bytes())
    return b3.unpack_bytes()

def send(packet_name, data = None):
    sock.sendall(pack_data({"name": packet_name, "params": data if data else {}}, c2s_types))

def unpack_packet():
    packet_len = 0
    for i in range(10):
        b = int(sock.recv(1)[0])
        packet_len |= (b & 0x7F) << 7 * i
        if not b & 0x80:
            break
    body = Buffer(sock.recv(packet_len), s2c_types)
    if compression_threshold >= 0:
        uncompressed_length = body.unpack_varint()
        if uncompressed_length > 0:
            body = Buffer(zlib.decompress(body.read()), s2c_types)
    return body.unpack("packet")

if __name__=="__main__":
    sock.connect(("127.0.0.1", 25565))
    update_state("handshaking")
    send("set_protocol", {'protocolVersion': 765, 'serverHost': 'localhost', 'serverPort': 25565, 'nextState': 1})
    update_state("status")
    send("ping_start", {})
    print(unpack_packet())

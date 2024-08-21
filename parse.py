"""
Reasons why i hate protodef
1. they dont have mapper in native for some reason
2. they randomly switcht from hex to normal numbers in mapper type
3. doesnt use snake_case
4. uses strings for all key (ok this is kinda unfair but still annyoing)


"""
from io import BytesIO
import struct
import uuid
import nbt
import nbt.nbt

MAX_VARNUM_LEN = 10

def to_snake_case(s: str):
    out = ""
    for c in s:
        if c.isupper():
            out += "_" + c.lower()
        else:
            out += c
    return out


class buffer:
    data = b""
    pos = 0
    types = {}
    container_stack = []

    def __init__(self, data: bytes | None = None, types=None) -> None:
        if data:
            self.data = data
        if types:
            self.types = types

    def pack_bytes(self, data):
        self.data += data

    def peek(self, method, *args, **kwargs):
        saved_pos = self.pos
        data = method(*args, **kwargs)
        self.pos = saved_pos
        return data

    def __len__(self):
        return len(self.data)

    def unpack_bytes(self, lenght=None):
        if len(self) - self.pos < lenght:
            raise IndexError("buffer not big egnouth")

        data = self.data[self.pos : self.pos + lenght if lenght else None]
        self.pos += lenght if lenght else len(self)
        return data

    def pack_c(self, fmt, *fields):
        self.pack_bytes(struct.pack(">" + fmt, *fields))

    def unpack_c(self, fmt):
        fmt = ">" + fmt
        data = self.unpack_bytes(struct.calcsize(fmt))
        data = struct.unpack(fmt, data)
        if len(data) == 1:
            return data[0]
        return data

    def unpack_u8(self):
        return self.unpack_c("B")

    def unpack_u16(self):
        return self.unpack_c("H")

    def unpack_u32(self):
        return self.unpack_c("I")

    def unpack_u64(self):
        return self.unpack_c("Q")

    def unpack_i8(self):
        return self.unpack_c("b")

    def unpack_i16(self):
        return self.unpack_c("h")

    def unpack_i32(self):
        return self.unpack_c("i")

    def unpack_i64(self):
        return self.unpack_c("q")

    def unpack_f32(self):
        return self.unpack_c("f")

    def unpack_f64(self):
        return self.unpack_c("d")

    def pack_u8(self, data):
        self.pack_c("B", data)

    def pack_u16(self, data):
        self.pack_c("H", data)

    def pack_u32(self, data):
        self.pack_c("I", data)

    def pack_u64(self, data):
        self.pack_c("Q", data)

    def pack_i8(self, data):
        self.pack_c("b", data)

    def pack_i16(self, data):
        self.pack_c("h", data)

    def pack_i32(self, data):
        self.pack_c("i", data)

    def pack_i64(self, data):
        self.pack_c("q", data)

    def pack_f32(self, data):
        self.pack_c("f", data)

    def pack_f64(self, data):
        self.pack_c("d", data)

    def unpack_bool(self):
        return self.unpack_c("?")

    def pack_bool(self, data):
        self.pack_c("?", data)

    def unpack_void(self):
        pass

    def pack_void(self):
        pass

    def unpack_uuid(self):
        return uuid.UUID(bytes=self.unpack_bytes(16))

    def pack_uuid(self, data: uuid.UUID):
        self.pack_bytes(data.bytes)

    def pack_varnum(self, number, max_bits):
        number_min = -1 << (max_bits - 1)
        number_max = +1 << (max_bits - 1)
        if not (number_min <= number < number_max):
            raise ValueError(
                f"varnum does not fit in range: {number_min:d} <= {number:d} < {number_max:d}"
            )

        if number < 0:
            number += 1 << 32

        for _ in range(10):
            b = number & 0x7F
            number >>= 7
            self.pack_c("B", b | (0x80 if number > 0 else 0))
            if number == 0:
                break

    def unpack_varnum(self, max_bits):
        number = 0
        for i in range(10):
            b = self.unpack_c("B")
            number |= (b & 0x7F) << 7 * i
            if not b & 0x80:
                break

        if number & (1 << 31):
            number -= 1 << 32

        number_min = -1 << (max_bits - 1)
        number_max = +1 << (max_bits - 1)
        if not (number_min <= number < number_max):
            raise ValueError(
                f"varnum does not fit in range: {number_min:d} <= {number:d} < {number_max:d}"
            )

        return number

    def unpack_varint(self):
        return self.unpack_varnum(32)

    def pack_varint(self, data):
        self.pack_varnum(data, 32)

    def unpack_varlong(self):
        return self.unpack_varnum(64)

    def pack_varlong(self, data):
        self.pack_varnum(data, 64)

    def unpack_rest_buffer(self):
        return self.unpack_bytes()
    
    def pack_rest_buffer(self, data):
        self.pack_bytes(data)

    def unpack_anonymous_nbt(self):
        buff = BytesIO(self.data[self.pos:])
        data = nbt.nbt.NBTFile(buffer=buff, network=True)
        self.pos += buff.tell()
        return data
    
    def pack_anonymous_nbt(self, data: nbt.nbt.NBTFile):
        buff = BytesIO()
        data.write_file(buffer=buff, network=True)
        self.pack_bytes(buff.read())

    def unpack_anon_optional_nbt(self):
        if not self.peek(self.unpack_u8):
            self.unpack_u8()
            return None
        return self.unpack_anonymous_nbt()
    
    def pack_anon_optional_nbt(self, data):
        if not data:
            self.pack_u8(0)
            return
        self.pack_anonymous_nbt(data)

    # protodef stuff

    def get_var(self, path):
        container_stack_index = -1
        data = self.container_stack[container_stack_index]
        for part in path.split("/"):
            if part == "..":
                container_stack_index -= 1
                data = self.container_stack[container_stack_index]                
            else:
                data[part] = data
        return data

    def unpack(self, protodef):
        data = None
        if type(protodef) is str:
            type_name = protodef
        else:
            type_name, data = protodef

        protodef = self.types[type_name]
        if protodef == "native":
            method = getattr(self, "unpack_" + to_snake_case(type_name))
            if data:
                return method(data)
            return method()
        else:
            return self.unpack(protodef)

    def pack(self, protodef, data):
        upacked_protodef = None
        if type(protodef) is str:
            type_name = protodef
        else:
            type_name, upacked_protodef = protodef

        protodef = self.types[type_name]
        if protodef == "native":
            method = getattr(self, "pack_" + type_name)
            if upacked_protodef:
                return method(upacked_protodef, data)
            return method(data)
        else:
            self.pack(protodef, data)

    def unpack_container(self, protodef):
        ret = {}
        self.container_stack.append(ret)
        for field in protodef:
            data = self.unpack(field["type"])
            if field.get("anon", False):
                ret.update(data)
            else:
                ret[field["name"]] = data
        self.container_stack.pop()

        return ret

    def pack_container(self, protodef, data):
        self.container_stack.append(data)
        for field in protodef:
            self.pack(field["type"], data[field["name"]])
        self.container_stack.pop()


    def unpack_switch(self, protodef):
        return self.unpack(protodef["fields"][str(self.get_var(protodef["compareTo"]))])

    def pack_switch(self, protodef, data):
        self.pack(protodef["fields"][str(self.get_var(protodef["compareTo"]))], data)

    def pack_pstring(self, protodef, data):
        getattr(self, "pack_" + protodef["countType"])(len(data))
        self.pack_bytes(data.encode("utf-8"))

    def unpack_pstring(self, protodef):
        lenght = getattr(self, "unpack_" + protodef["countType"])()
        return str(self.unpack_bytes(lenght), encoding="utf-8")

    def unpack_option(self, protodef):
        if self.unpack_bool():
            return self.unpack(protodef)

    def pack_option(self, protodef, data):
        self.pack_bool(bool(data))
        if data:
            self.pack(protodef, data)

    def unpack_bitfield(self, protodef):
        funcmap = {
            8: self.unpack_u8,
            16: self.unpack_u16,
            32: self.unpack_u32,
            64: self.unpack_u64,
        }
        ret = {}
        pos = 0
        total_size = sum([field["size"] for field in protodef])
        data = funcmap[total_size]()

        ret = {}
        for field in protodef:
            size = field["size"]
            res = (data >> (total_size - pos - size)) & 2**size - 1
            if field["signed"] and res >= 1 << (size - 1):
                res -= 1 << size
            ret[field["name"]] = res
            pos += size

        return ret

    def pack_bitfield(self, protodef, data):
        funcmap = {
            8: self.pack_u8,
            16: self.pack_u16,
            32: self.pack_u32,
            64: self.pack_u64,
        }

        ret = 0
        pos = 0
        total_size = sum([field["size"] for field in protodef])
        for field in protodef:
            size = field["size"]
            num = data[field["name"]]
            if num < 0:
                num += 1 << size
            ret |= num << (total_size - size - pos)
            pos += size

        funcmap[total_size](ret)

    def pack_array(self, protodef, data):
        getattr(self, "pack_" + protodef["countType"])(len(data))
        for element in data:
            self.pack(protodef["type"], element)

    def unpack_array(self, protodef):
        lenght = getattr(self, "unpack_" + protodef["countType"])()
        ret = []
        for _ in range(lenght):
            ret.append(self.unpack(protodef["type"]))
        return ret

    def unpack_buffer(self, protodef):
        lenght = protodef.get("count", None)
        if lenght is None:
            lenght = getattr(self, "unpack_" + protodef["countType"])()
        return self.unpack_bytes(lenght)

    def pack_buffer(self, protodef, data):
        if "countType" in protodef:
            getattr(self, "pack_" + protodef["countType"])(len(data))
        self.pack_bytes(data)

    def pack_entity_metadata_loop(self, protodef, data):
        for index in data:
            self.pack_u8(index)
            self.pack(protodef["type"], data[index])
        self.pack_u8(protodef["endVal"])

    def unpack_entity_metadata_loop(self, protodef):
        ret = {}
        while True:
            index = self.unpack_u8()
            if index == protodef["endVal"]:
                break
            ret[index] = self.unpack(protodef["type"])
        return ret
    
    def unpack_top_bit_set_terminated_array(self, protodef):
        ret = []
        while True:
            saved_pos = self.pos
            saved_byte = self.data[self.pos]
            self.data[self.pos] &= 0x7F
            ret.append(self.unpack(protodef["type"]))
            self.data[saved_pos]
            if saved_byte & 0x80:
                break
        
        return ret
    
    def pack_top_bit_set_terminated_array(self, protodef, data):
        for i, element in enumerate(data):
            old_pos = len(self)
            self.pack(protodef["type"], element)
            if len(element) - 1 == i:
                self.data[old_pos] |= 0x80

    def unpack_mapper(self, protodef):
        data = getattr(self, "unpack_" + protodef["type"])()
        for mapping in protodef["mappings"]:
            if eval(mapping) == data: # ik eval bad BUUUUTTT no
                return protodef["mappings"][mapping]

    def pack_mapper(self, protodef, data):
        for mapping in protodef["mappings"]:
            if protodef["mappings"][mapping] == data:
                getattr(self, "pack_" + protodef["type"])(eval(mapping))

class connection:
    def __init__(self, proto, state, direction) -> None:
        self._proto = proto
        self._state = state
        self._direction = direction
    
    def set_state(self, state):
        self._state = state
        types = self._proto["types"]
        types.update(self._proto[self._state][self._direction]["types"])
        return types
    

if __name__ == "__main__":
    import json

    with open("minecraft-data/data/pc/1.20.3/protocol.json", "r") as f:
        proto = json.load(f)

    handshake = buffer(b"\375\005\tlocalhostc\335\001", proto["types"])
    print(handshake.data)
    data = handshake.unpack(
        proto["handshaking"]["toServer"]["types"]["packet_set_protocol"]
    )
    print(data)
    newbuffer = buffer(types=proto["types"])
    newbuffer.pack(
        proto["handshaking"]["toServer"]["types"]["packet_set_protocol"], data
    )
    print(newbuffer.data)

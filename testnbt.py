from buffer import Buffer

def readfile(file_path):
    with open(file_path, "rb") as f:
        return f.read()
    
hello_world = Buffer(readfile("testdata/hello_world.nbt"))
bigtest = Buffer(readfile("testdata/bigtest.nbt"))

hello_world_data = hello_world.unpack_nbt()
print(hello_world_data)

big_data = bigtest.unpack_nbt()
print(big_data)

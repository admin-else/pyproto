import json
import pyproto
from os import path

PATH = path.join(pyproto.__path__[0], "minecraft-data/data/")
PATH_DATA = path.join(PATH, "dataPaths.json")
COMMON_DATA = path.join(PATH, "pc/common")

with open(PATH_DATA) as f:
    PATHS = json.load(f)


def get(version, data):
    data_path = PATHS["pc"].get(version, {}).get(data)
    if not data_path:
        raise FileNotFoundError(f"no data for {version}/{data}")
    data_path = path.join(PATH, data_path, data) + ".json"
    with open(data_path) as f:
        return json.load(f)


def common(data):
    with open(path.join(COMMON_DATA, data) + ".json") as f:
        return json.load(f)

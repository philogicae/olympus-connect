import json

_CONFIG = None


def get_config():
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG
    try:
        with open("config.json") as f:
            _CONFIG = json.load(f)
    except FileNotFoundError, json.JSONDecodeError:
        _CONFIG = {}
    return _CONFIG

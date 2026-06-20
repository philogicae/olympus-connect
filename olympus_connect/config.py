import json
import os

_CONFIG = None


def get_config():
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG
    _CONFIG = {}
    for p in [
        "config.json",
        os.path.expanduser("~/.config/olympus-connect/config.json"),
    ]:
        try:
            with open(p) as f:
                _CONFIG = json.load(f)
                break
        except FileNotFoundError, json.JSONDecodeError:
            continue
    return _CONFIG

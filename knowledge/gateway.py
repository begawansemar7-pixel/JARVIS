"""Policy gateway for keeping sensitive context on approved runtimes."""
from __future__ import annotations

LEVELS = {"PUBLIC": 0, "INTERNAL": 1, "CONFIDENTIAL": 2, "SECRET": 3, "TOP_SECRET": 4}

CLOUD_MAX = LEVELS["CONFIDENTIAL"]


def route(classification: str, *, private_runtime: bool = False) -> str:
    """Select a runtime without ever routing SECRET/TOP_SECRET to cloud by default."""
    level = LEVELS.get(classification.upper(), 99)
    if level > CLOUD_MAX:
        if not private_runtime:
            raise PermissionError("SECRET/TOP_SECRET requires a private runtime")
        return "private"
    return "cloud"

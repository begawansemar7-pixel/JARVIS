"""Policy gateway for keeping sensitive context on approved runtimes."""
from __future__ import annotations

from .private_brain import Classification


def route(
    classification: str | Classification,
    *,
    private_runtime: bool = False,
    max_cloud: Classification = Classification.CONFIDENTIAL,
) -> str:
    """Select a runtime without ever routing above `max_cloud` to cloud."""
    try:
        level = Classification.parse(classification)
    except ValueError:
        level = None  # unknown labels are treated as the most restrictive
    if level is None or level > max_cloud:
        if not private_runtime:
            raise PermissionError(f"classification above {max_cloud.name} requires a private runtime")
        return "private"
    return "cloud"

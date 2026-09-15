from __future__ import annotations

import os
from typing import Any


class TaniaCapabilityClient:
    """Best-effort TANIA capability-status adapter.

    TANIA remains an external system of record. When TANIA_API_URL is absent,
    updates are represented as no-op acknowledgements so local development and
    tests remain deterministic.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or os.getenv("TANIA_API_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("TANIA_API_KEY")

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def update_capability_status(self, *, gap_id: str | None, capability_id: str | None,
                                 learner_id: str, status: str, skill_id: str,
                                 sprint_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "gap_id": gap_id,
            "capability_id": capability_id,
            "learner_id": learner_id,
            "skill_id": skill_id,
            "sprint_id": sprint_id,
            "status": status,
            "metadata": metadata or {},
        }
        if not self.enabled:
            return {"ok": True, "updated": False, "mode": "disabled", "payload": payload}

        import requests

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.post(
            f"{self.base_url}/capability-status",
            json=payload,
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json() if response.content else {}
        return {"ok": True, "updated": True, "mode": "http", "response": data}

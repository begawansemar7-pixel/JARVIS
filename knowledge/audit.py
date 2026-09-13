"""Redacted audit events for Private Brain access decisions.

Events carry identifiers, decisions and reasons only — never document content,
titles or search queries.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class AccessEvent:
    subject: str
    document_id: str
    action: str
    decision: str
    reason: str
    timestamp: str
    classification: str = ""

    @classmethod
    def now(
        cls, subject: str, document_id: str, action: str, decision: str, reason: str,
        classification: str = "",
    ) -> "AccessEvent":
        return cls(subject, document_id, action, decision, reason,
                   datetime.now(timezone.utc).isoformat(), classification)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class AuditLogger:
    """Append-only JSONL audit log, readable only by the file owner (0600)."""

    def __init__(self, path: str | Path | None, enabled: bool = True):
        self.path = Path(path) if path else None
        self.enabled = enabled and self.path is not None
        self._lock = threading.Lock()

    def record(self, event: AccessEvent) -> None:
        if not self.enabled:
            return
        line = json.dumps(event.to_dict(), ensure_ascii=False) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as f:
                f.write(line)


__all__ = ["AccessEvent", "AuditLogger"]

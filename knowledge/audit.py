"""Redacted audit events for Private Brain access decisions."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class AccessEvent:
    subject: str
    document_id: str
    action: str
    decision: str
    reason: str
    timestamp: str

    @classmethod
    def now(cls, subject: str, document_id: str, action: str, decision: str, reason: str) -> "AccessEvent":
        return cls(subject, document_id, action, decision, reason, datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


__all__ = ["AccessEvent"]

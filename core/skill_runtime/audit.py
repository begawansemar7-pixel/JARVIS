from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass(frozen=True)
class SkillAuditEvent:
    event: str
    skill_id: str
    correlation_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: dict[str, Any] = field(default_factory=dict)


class SkillAudit:
    def __init__(self, sink: Callable[[SkillAuditEvent], None] | None = None) -> None:
        self.events: list[SkillAuditEvent] = []
        self.sink = sink

    def emit(self, event: str, skill_id: str, *, correlation_id: str = "", **data: Any) -> SkillAuditEvent:
        item = SkillAuditEvent(event, skill_id, correlation_id, data=data)
        self.events.append(item)
        if self.sink:
            self.sink(item)
        return item

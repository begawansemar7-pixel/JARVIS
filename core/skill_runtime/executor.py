from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .models import SkillContext, SkillRecord


class SkillExecutor:
    """Execution boundary for skills.

    The executor intentionally accepts an injected runner. It does not import
    or execute arbitrary Python from a skill package. A future integration can
    connect this boundary to JARVIS's existing action/plugin governance.
    """

    def __init__(self, runner: Callable[[SkillRecord, str, SkillContext], Any] | None = None) -> None:
        self.runner = runner

    def execute(self, record: SkillRecord, instructions: str, context: SkillContext) -> Any:
        if record.manifest.status != "ACTIVE":
            raise PermissionError(f"skill is not ACTIVE: {record.skill_id}")
        if self.runner is None:
            return {
                "status": "planned",
                "skill": record.skill_id,
                "message": "Skill loaded successfully; no execution runner is attached.",
            }
        return self.runner(record, instructions, context)

from __future__ import annotations

from pathlib import Path

from .models import SkillRecord


class SkillLoader:
    """Loads declarative skill resources without executing package code."""

    def load_instructions(self, record: SkillRecord) -> str:
        if not record.valid:
            raise ValueError(f"cannot load invalid skill: {record.error}")
        text = record.instructions_path.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError(f"empty SKILL.md: {record.instructions_path}")
        return text

    def read_reference(self, record: SkillRecord, relative_path: str) -> str:
        target = (record.root / relative_path).resolve()
        if record.root.resolve() not in target.parents:
            raise ValueError("reference path escapes skill root")
        if not target.is_file():
            raise FileNotFoundError(relative_path)
        return target.read_text(encoding="utf-8")

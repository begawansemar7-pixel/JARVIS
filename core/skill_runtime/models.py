from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SkillManifest:
    name: str
    version: str
    category: str
    description: str
    triggers: tuple[str, ...] = ()
    risk_level: str = "low"
    requires_actions: tuple[str, ...] = ()
    requires_plugins: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    confirmation: bool = False
    permissions: tuple[str, ...] = ()
    data_classification: str = "internal"
    status: str = "DRAFT"
    author: str = ""


@dataclass
class SkillRecord:
    manifest: SkillManifest
    root: Path
    instructions_path: Path
    checksum: str = ""
    valid: bool = True
    error: str = ""

    @property
    def skill_id(self) -> str:
        return f"{self.manifest.name}@{self.manifest.version}"


@dataclass(frozen=True)
class SkillContext:
    task: str
    inputs: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    correlation_id: str = ""
    available_actions: frozenset[str] = frozenset()
    available_plugins: frozenset[str] = frozenset()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillResolution:
    selected: SkillRecord | None
    candidates: tuple[SkillRecord, ...] = ()
    reason: str = ""

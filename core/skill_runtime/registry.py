from __future__ import annotations

from collections.abc import Iterable

from .models import SkillRecord


class SkillRegistry:
    """In-process registry of validated skills; never executes them."""

    def __init__(self, records: Iterable[SkillRecord] = ()) -> None:
        self._records: dict[str, SkillRecord] = {}
        self._by_name: dict[str, SkillRecord] = {}
        for record in records:
            self.register(record)

    def register(self, record: SkillRecord) -> None:
        if not record.valid:
            raise ValueError(f"cannot register invalid skill: {record.error}")
        if record.skill_id in self._records:
            raise ValueError(f"duplicate skill identity: {record.skill_id}")
        if record.manifest.status == "ACTIVE" and record.manifest.name in self._by_name:
            current = self._by_name[record.manifest.name]
            raise ValueError(
                f"multiple ACTIVE versions for {record.manifest.name}: "
                f"{current.manifest.version} and {record.manifest.version}"
            )
        self._records[record.skill_id] = record
        if record.manifest.status == "ACTIVE":
            self._by_name[record.manifest.name] = record

    def get(self, skill_id: str) -> SkillRecord | None:
        return self._records.get(skill_id)

    def get_active(self, name: str) -> SkillRecord | None:
        return self._by_name.get(name)

    def all(self, active_only: bool = False) -> tuple[SkillRecord, ...]:
        records = tuple(self._records.values())
        if active_only:
            return tuple(r for r in records if r.manifest.status == "ACTIVE")
        return records

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_name))

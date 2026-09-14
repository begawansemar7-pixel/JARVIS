from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .integrity import package_checksum, verify_checksum
from .models import SkillRecord
from .validator import SkillValidationError, validate_manifest


class SkillDiscovery:
    def __init__(self, registry_path: Path, lock_path: Path | None = None,
                 logger: Callable[[str], None] = print) -> None:
        self.registry_path = registry_path
        self.lock_path = lock_path
        self.logger = logger

    def discover(self, skills_root: Path) -> tuple[SkillRecord, ...]:
        catalog = self._read_json(self.registry_path)
        lock = self._read_json(self.lock_path) if self.lock_path else {}
        records: list[SkillRecord] = []
        for entry in catalog.get("skills", []):
            try:
                name = entry["name"]
                version = entry["version"]
                manifest_data = entry.get("manifest", entry)
                manifest = validate_manifest(manifest_data)
                if manifest.name != name or manifest.version != version:
                    raise SkillValidationError("registry identity does not match manifest")
                root = (skills_root / entry.get("path", f"{manifest.category}/{manifest.name}")).resolve()
                root_guard = skills_root.resolve()
                if root != root_guard and root_guard not in root.parents:
                    raise SkillValidationError("skill path escapes skills root")
                instructions = root / "SKILL.md"
                if not instructions.is_file():
                    raise SkillValidationError("SKILL.md is missing")

                expected = lock.get("skills", {}).get(f"{name}@{version}", {}).get("checksum", "")
                checksum = package_checksum(root)
                if expected and not verify_checksum(root, expected):
                    raise SkillValidationError("package checksum mismatch")
                records.append(SkillRecord(manifest, root, instructions, checksum))
                self.logger(f"Skill discovered: {name}@{version}")
            except (KeyError, TypeError, ValueError, OSError) as exc:
                self.logger(f"Skill rejected: {entry!r} — {exc}")
        return tuple(records)

    @staticmethod
    def _read_json(path: Path | None) -> dict:
        if path is None or not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError(f"expected object in {path}")
        return value

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.skill_runtime.models import SkillDefinition


def _scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return None
    if value in ("[]", "{}"):
        return [] if value == "[]" else {}
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        if value.startswith("[") and value.endswith("]"):
            return [x.strip().strip("'\"") for x in value[1:-1].split(",") if x.strip()]
        return value


def parse_yaml_subset(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    target: dict[str, Any] = data
    current_list: list | None = None
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip()
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if stripped.startswith("-") and current_list is not None:
            current_list.append(_scalar(stripped[1:].strip()))
            continue
        key, raw_value = stripped.split(":", 1)
        key, raw_value = key.strip(), raw_value.strip()
        if indent == 0:
            target = data
            if raw_value:
                data[key] = _scalar(raw_value)
                current_list = None
            else:
                data[key] = []
                current_list = data[key]
        else:
            if key == "assessment":
                data["assessment"] = {}
                target = data["assessment"]
                current_list = None
            elif target is data.get("assessment"):
                if raw_value:
                    target[key] = _scalar(raw_value)
                    current_list = None
                else:
                    target[key] = []
                    current_list = target[key]
    return data


def load_registry(directory: str | Path = "skill-registry/skills") -> dict[str, SkillDefinition]:
    root = Path(directory)
    result: dict[str, SkillDefinition] = {}
    for path in sorted(root.glob("*.yaml")):
        raw = parse_yaml_subset(path.read_text(encoding="utf-8"))
        skill = SkillDefinition(
            skill_id=str(raw["skill_id"]), name=str(raw["name"]), domain=str(raw["domain"]),
            level=str(raw["level"]), target_performance=list(raw.get("target_performance", [])),
            prerequisites=list(raw.get("prerequisites", [])), target_hours=float(raw.get("target_hours", 20)),
            assessment=dict(raw.get("assessment", {})), version=str(raw.get("version", "1.0.0")),
        )
        result[skill.skill_id] = skill
    return result

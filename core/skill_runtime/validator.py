from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import SkillManifest

NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
RISK_LEVELS = {"low", "medium", "high", "critical"}
STATUSES = {"DRAFT", "VALIDATING", "CERTIFIED", "ACTIVE", "DEPRECATED", "RETIRED"}


class SkillValidationError(ValueError):
    pass


def validate_manifest(data: dict[str, Any]) -> SkillManifest:
    if not isinstance(data, dict):
        raise SkillValidationError("manifest must be an object")

    required = ("name", "version", "category", "description", "triggers", "risk_level", "requires", "outputs", "governance")
    missing = [key for key in required if key not in data]
    if missing:
        raise SkillValidationError(f"missing required fields: {', '.join(missing)}")

    name = data["name"]
    version = data["version"]
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise SkillValidationError("name must match ^[a-z][a-z0-9_-]{1,63}$")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise SkillValidationError("version must be semantic-version shaped")

    for key in ("category", "description"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise SkillValidationError(f"{key} must be a non-empty string")

    triggers = _string_tuple(data["triggers"], "triggers")
    outputs = _string_tuple(data["outputs"], "outputs")
    requires = data["requires"]
    if not isinstance(requires, dict):
        raise SkillValidationError("requires must be an object")
    actions = _string_tuple(requires.get("actions", []), "requires.actions")
    plugins = _string_tuple(requires.get("plugins", []), "requires.plugins")

    governance = data["governance"]
    if not isinstance(governance, dict):
        raise SkillValidationError("governance must be an object")
    confirmation = governance.get("confirmation", False)
    if not isinstance(confirmation, bool):
        raise SkillValidationError("governance.confirmation must be boolean")

    risk = data["risk_level"]
    if risk not in RISK_LEVELS:
        raise SkillValidationError(f"risk_level must be one of {sorted(RISK_LEVELS)}")

    status = data.get("status", "DRAFT")
    if status not in STATUSES:
        raise SkillValidationError(f"status must be one of {sorted(STATUSES)}")

    permissions = _string_tuple(data.get("permissions", governance.get("permissions", [])), "permissions")
    data_classification = data.get("data_classification", "internal")
    if not isinstance(data_classification, str) or not data_classification.strip():
        raise SkillValidationError("data_classification must be a non-empty string")

    return SkillManifest(
        name=name,
        version=version,
        category=data["category"].strip(),
        description=data["description"].strip(),
        triggers=triggers,
        risk_level=risk,
        requires_actions=actions,
        requires_plugins=plugins,
        outputs=outputs,
        confirmation=confirmation,
        permissions=permissions,
        data_classification=data_classification.strip(),
        status=status,
        author=str(data.get("author", "")),
    )


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise SkillValidationError(f"{field_name} must be a list of non-empty strings")
    return tuple(v.strip() for v in value)

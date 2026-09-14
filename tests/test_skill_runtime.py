from pathlib import Path

import pytest

from core.skill_runtime.models import SkillRecord
from core.skill_runtime.registry import SkillRegistry
from core.skill_runtime.validator import SkillValidationError, validate_manifest


def manifest(status="ACTIVE"):
    return {
        "name": "test-skill",
        "version": "1.0.0",
        "category": "builtin",
        "description": "test",
        "triggers": ["test skill"],
        "risk_level": "low",
        "requires": {"actions": [], "plugins": []},
        "outputs": ["result"],
        "governance": {"confirmation": False},
        "status": status,
    }


def record(status="ACTIVE"):
    m = validate_manifest(manifest(status))
    root = Path("skills/builtin/test-skill")
    return SkillRecord(m, root, root / "SKILL.md", valid=True)


def test_manifest_validation():
    result = validate_manifest(manifest())
    assert result.name == "test-skill"
    assert result.risk_level == "low"


def test_invalid_manifest_rejected():
    data = manifest()
    data["risk_level"] = "unsafe"
    with pytest.raises(SkillValidationError):
        validate_manifest(data)


def test_registry_resolves_active_skill():
    registry = SkillRegistry([record()])
    assert registry.get_active("test-skill").skill_id == "test-skill@1.0.0"


def test_registry_rejects_two_active_versions():
    first = record()
    data = manifest()
    data["version"] = "2.0.0"
    second_manifest = validate_manifest(data)
    second = SkillRecord(second_manifest, Path("skills/builtin/test-skill-v2"), Path("skills/builtin/test-skill-v2/SKILL.md"))
    registry = SkillRegistry([first])
    with pytest.raises(ValueError, match="multiple ACTIVE versions"):
        registry.register(second)

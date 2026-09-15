from pathlib import Path

import pytest

from core.skill_runtime.models import SkillDefinition
from core.skill_runtime.repository import SQLiteSkillRepository
from core.skill_runtime.service import SkillRuntime
from skill_registry.loader import load_registry


ROOT = Path(__file__).resolve().parents[2]


def runtime(tmp_path):
    registry = load_registry(ROOT / "skill-registry" / "skills")
    return SkillRuntime(registry, SQLiteSkillRepository(tmp_path / "skills.db"))


def test_prerequisite_blocks_rag_until_llm_verified(tmp_path):
    rt = runtime(tmp_path)
    with pytest.raises(ValueError, match="AI-LLM-001"):
        rt.start_sprint("AI-RAG-001", "talent-1")


def test_same_idempotency_key_returns_same_sprint(tmp_path):
    rt = runtime(tmp_path)
    first = rt.start_sprint("AI-LLM-001", "talent-1", idempotency_key="tania-gap-1")
    second = rt.start_sprint("AI-LLM-001", "talent-1", idempotency_key="tania-gap-1")
    assert first.sprint_id == second.sprint_id
    assert len(rt.repository.list_sprints("talent-1")) == 1


def test_tania_gap_starts_skill_sprint_and_audits_source(tmp_path):
    rt = runtime(tmp_path)
    sprint = rt.start_from_capability_gap({
        "gap_id": "gap-42",
        "learner_id": "talent-9",
        "capability_id": "CAP-AI-RAG",
        "required_skill_id": "AI-LLM-001",
        "priority": "P1",
    })
    assert sprint.skill_id == "AI-LLM-001"
    events = rt.audit(sprint.sprint_id)
    assert events[0]["event_type"] == "sprint.started"
    assert events[0]["payload"]["source"]["system"] == "TANIA"
    assert events[0]["payload"]["source"]["gap_id"] == "gap-42"

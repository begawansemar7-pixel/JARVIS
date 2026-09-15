from core.skill_runtime.models import Evidence
from core.skill_runtime.repository import SQLiteSkillRepository
from core.skill_runtime.service import SkillRuntime
from core.skill_runtime.models import SkillDefinition


def _skill():
    return SkillDefinition(
        skill_id="TEST-001", name="Test", domain="AI", level="foundation",
        target_performance=["demo"], target_hours=4,
        assessment={"required_evidence": ["demo"]}, version="1.0.0"
    )


def test_sqlite_roundtrip(tmp_path):
    repo = SQLiteSkillRepository(tmp_path / "skills.db")
    runtime = SkillRuntime({"TEST-001": _skill()}, repo)
    sprint = runtime.start_sprint("TEST-001", "learner-1")
    runtime.begin_practice(sprint.sprint_id)
    runtime.log_practice(sprint.sprint_id, 2)
    runtime.add_evidence(sprint.sprint_id, Evidence("e1", "demo", "Demo", 90, {}))

    restored = SkillRuntime({"TEST-001": _skill()}, repo).get(sprint.sprint_id)
    assert restored.state == "practice"
    assert restored.hours_completed == 2
    assert restored.evidence[0].kind == "demo"

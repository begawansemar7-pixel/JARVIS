from pathlib import Path

from core.skill_runtime.execution import SkillExecutionEngine
from core.skill_runtime.planner import SprintStep
from core.skill_runtime.repository import SQLiteSkillRepository
from core.skill_runtime.service import SkillRuntime
from skill_registry.loader import load_registry


ROOT = Path(__file__).resolve().parents[2]


def test_plan_step_is_executed_and_creates_evidence(tmp_path):
    registry = load_registry(ROOT / "skill-registry" / "skills")
    runtime = SkillRuntime(registry, SQLiteSkillRepository(tmp_path / "skills.db"))
    sprint = runtime.start_sprint("AI-LLM-001", "talent-1")
    runtime.begin_practice(sprint.sprint_id)

    calls = []

    def dispatch(name, parameters):
        calls.append((name, parameters))
        return '{"success": true, "result": "completed", "deliverable": "artifact"}'

    engine = SkillExecutionEngine(dispatch, runtime)
    plan = engine.build_plan(registry["AI-LLM-001"], runtime.get(sprint.sprint_id), [
        SprintStep(1, "build", 2.0, "Build a small LLM exercise", "Implement and test it", "working artifact")
    ])
    result = engine.execute(plan, idempotency_prefix="exec-1")

    assert result.status == "completed"
    assert calls[0][0] == "skill_step_executor"
    current = runtime.get(sprint.sprint_id)
    assert current.hours_completed == 2.0
    assert len(current.evidence) == 1
    assert current.evidence[0].kind == "execution:build"


def test_failed_action_does_not_advance_practice(tmp_path):
    registry = load_registry(ROOT / "skill-registry" / "skills")
    runtime = SkillRuntime(registry, SQLiteSkillRepository(tmp_path / "skills.db"))
    sprint = runtime.start_sprint("AI-LLM-001", "talent-1")
    runtime.begin_practice(sprint.sprint_id)

    def dispatch(name, parameters):
        return "Tool 'skill_step_executor' failed: unavailable"

    engine = SkillExecutionEngine(dispatch, runtime)
    plan = engine.build_plan(registry["AI-LLM-001"], sprint, [
        SprintStep(1, "practice", 2.0, "Practice", "Run exercise", "test output")
    ])
    result = engine.execute(plan)

    assert result.status == "failed"
    current = runtime.get(sprint.sprint_id)
    assert current.hours_completed == 0
    assert current.evidence == []

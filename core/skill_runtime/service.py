from __future__ import annotations
from uuid import uuid4
from .models import SkillDefinition, SkillSprint, AssessmentResult, Evidence
from .states import transition
from .scoring import is_verified
from .repository import SkillRepository


class SkillRuntime:
    """Authoritative skill execution runtime.

    Storage is injected so the same runtime works with in-memory tests, SQLite,
    or Supabase. The runtime, not the planner/LLM, owns capability state.
    """
    def __init__(self, registry: dict[str, SkillDefinition], repository: SkillRepository | None = None):
        self.registry = registry
        self.repository = repository
        self.sprints: dict[str, SkillSprint] = {}

    def _load(self, sprint_id: str) -> SkillSprint:
        if sprint_id in self.sprints:
            return self.sprints[sprint_id]
        if self.repository:
            sprint = self.repository.get_sprint(sprint_id)
            if sprint:
                self.sprints[sprint_id] = sprint
                return sprint
        raise KeyError(f"Sprint '{sprint_id}' not found")

    def _save(self, sprint: SkillSprint) -> SkillSprint:
        self.sprints[sprint.sprint_id] = sprint
        if self.repository:
            self.repository.save_sprint(sprint)
        return sprint

    def start_sprint(self, skill_id: str, learner_id: str) -> SkillSprint:
        skill = self.registry.get(skill_id)
        if skill is None:
            raise KeyError(f"Skill '{skill_id}' is not registered")
        sprint = SkillSprint(uuid4().hex, skill.skill_id, learner_id)
        sprint.state = transition(sprint.state, "start")
        return self._save(sprint)

    def begin_practice(self, sprint_id: str) -> SkillSprint:
        sprint = self._load(sprint_id)
        sprint.state = transition(sprint.state, "begin_practice")
        return self._save(sprint)

    def log_practice(self, sprint_id: str, hours: float) -> SkillSprint:
        if hours <= 0:
            raise ValueError("Practice hours must be positive")
        sprint = self._load(sprint_id)
        if sprint.state != "practice":
            raise ValueError("Practice can only be logged in practice state")
        skill = self.registry[sprint.skill_id]
        sprint.hours_completed = round(min(float(skill.target_hours), sprint.hours_completed + hours), 2)
        return self._save(sprint)

    def add_evidence(self, sprint_id: str, evidence: Evidence) -> SkillSprint:
        sprint = self._load(sprint_id)
        if sprint.state != "practice":
            raise ValueError("Evidence can only be added in practice state")
        if not 0 <= evidence.score <= 100:
            raise ValueError("Evidence score must be 0..100")
        sprint.evidence.append(evidence)
        return self._save(sprint)

    def submit_assessment(self, sprint_id: str, result: AssessmentResult) -> SkillSprint:
        sprint = self._load(sprint_id)
        if sprint.state != "practice":
            raise ValueError("Assessment can only be submitted from practice state")
        skill = self.registry[sprint.skill_id]
        required = set(skill.assessment.get("required_evidence", []))
        present = {e.kind for e in sprint.evidence}
        missing = sorted(required - present)
        if missing:
            raise ValueError(f"Missing required evidence: {', '.join(missing)}")
        sprint.state = transition(sprint.state, "submit_assessment")
        result.passed = is_verified(result)
        if result.passed and sprint.hours_completed < skill.target_hours:
            result.passed = False
            result.feedback = (result.feedback + " " if result.feedback else "") + f"Complete the {skill.target_hours}-hour sprint before verification."
        sprint.assessment = result
        sprint.state = transition(sprint.state, "pass" if result.passed else "fail")
        return self._save(sprint)

    def retry(self, sprint_id: str) -> SkillSprint:
        sprint = self._load(sprint_id)
        sprint.state = transition(sprint.state, "retry")
        return self._save(sprint)

    def get(self, sprint_id: str) -> SkillSprint:
        return self._load(sprint_id)

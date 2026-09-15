from __future__ import annotations

from typing import Any, Callable
from uuid import uuid4

from .models import SkillDefinition, SkillSprint, AssessmentResult, Evidence
from .states import transition
from .scoring import is_verified
from .repository import SkillRepository, sprint_to_dict


class SkillRuntime:
    """Authoritative skill execution runtime.

    The runtime owns lifecycle, prerequisites, verification, idempotency and
    audit events. LLM/planner output is advisory and never changes state.
    """
    def __init__(self, registry: dict[str, SkillDefinition], repository: SkillRepository | None = None):
        self.registry = registry
        self.repository = repository
        self.sprints: dict[str, SkillSprint] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self.events: list[dict[str, Any]] = []

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

    def _event(self, event_type: str, sprint: SkillSprint | None = None,
               idempotency_key: str | None = None, payload: dict[str, Any] | None = None) -> None:
        event = {
            "event_id": uuid4().hex,
            "event_type": event_type,
            "sprint_id": sprint.sprint_id if sprint else None,
            "skill_id": sprint.skill_id if sprint else None,
            "learner_id": sprint.learner_id if sprint else None,
            "idempotency_key": idempotency_key,
            "payload": payload or {},
        }
        self.events.append(event)
        if self.repository:
            try:
                self.repository.append_event(event)
            except (AttributeError, NotImplementedError):
                pass

    def _idempotent(self, operation: str, key: str | None, fn: Callable[[], SkillSprint]) -> SkillSprint:
        if not key:
            return fn()
        cache_key = (operation, key)
        sprint_id = self._idempotency.get(cache_key)
        if sprint_id:
            return self._load(sprint_id)
        if self.repository:
            try:
                sprint_id = self.repository.get_idempotency(key, operation)
            except (AttributeError, NotImplementedError):
                sprint_id = None
            if sprint_id:
                self._idempotency[cache_key] = sprint_id
                return self._load(sprint_id)
        sprint = fn()
        self._idempotency[cache_key] = sprint.sprint_id
        if self.repository:
            try:
                self.repository.save_idempotency(key, operation, sprint.sprint_id)
            except (AttributeError, NotImplementedError):
                pass
        return sprint

    def _verified(self, learner_id: str, skill_id: str) -> bool:
        for sprint in self.sprints.values():
            if sprint.learner_id == learner_id and sprint.skill_id == skill_id and sprint.state == "verified":
                return True
        if self.repository:
            return any(s.learner_id == learner_id and s.skill_id == skill_id and s.state == "verified"
                       for s in self.repository.list_sprints(learner_id))
        return False

    def _check_prerequisites(self, skill: SkillDefinition, learner_id: str) -> None:
        missing = [p for p in skill.prerequisites if not self._verified(learner_id, p)]
        if missing:
            raise ValueError(
                f"Prerequisite skills not verified for learner '{learner_id}': {', '.join(missing)}"
            )

    def start_sprint(self, skill_id: str, learner_id: str, idempotency_key: str | None = None,
                     source: dict[str, Any] | None = None) -> SkillSprint:
        def create() -> SkillSprint:
            skill = self.registry.get(skill_id)
            if skill is None:
                raise KeyError(f"Skill '{skill_id}' is not registered")
            self._check_prerequisites(skill, learner_id)
            sprint = SkillSprint(uuid4().hex, skill.skill_id, learner_id)
            sprint.state = transition(sprint.state, "start")
            saved = self._save(sprint)
            self._event("sprint.started", saved, idempotency_key, {"source": source or "direct"})
            return saved
        return self._idempotent("start", idempotency_key, create)

    def begin_practice(self, sprint_id: str, idempotency_key: str | None = None) -> SkillSprint:
        def mutate() -> SkillSprint:
            sprint = self._load(sprint_id)
            sprint.state = transition(sprint.state, "begin_practice")
            saved = self._save(sprint)
            self._event("practice.started", saved, idempotency_key)
            return saved
        return self._idempotent("begin_practice", idempotency_key, mutate)

    def log_practice(self, sprint_id: str, hours: float, idempotency_key: str | None = None) -> SkillSprint:
        if hours <= 0:
            raise ValueError("Practice hours must be positive")
        def mutate() -> SkillSprint:
            sprint = self._load(sprint_id)
            if sprint.state != "practice":
                raise ValueError("Practice can only be logged in practice state")
            skill = self.registry[sprint.skill_id]
            previous = sprint.hours_completed
            sprint.hours_completed = round(min(float(skill.target_hours), sprint.hours_completed + hours), 2)
            saved = self._save(sprint)
            self._event("practice.logged", saved, idempotency_key,
                         {"hours_requested": hours, "hours_added": round(saved.hours_completed - previous, 2)})
            return saved
        return self._idempotent("log_practice", idempotency_key, mutate)

    def add_evidence(self, sprint_id: str, evidence: Evidence, idempotency_key: str | None = None) -> SkillSprint:
        def mutate() -> SkillSprint:
            sprint = self._load(sprint_id)
            if sprint.state != "practice":
                raise ValueError("Evidence can only be added in practice state")
            if not 0 <= evidence.score <= 100:
                raise ValueError("Evidence score must be 0..100")
            if any(e.evidence_id == evidence.evidence_id for e in sprint.evidence):
                return sprint
            sprint.evidence.append(evidence)
            saved = self._save(sprint)
            self._event("evidence.added", saved, idempotency_key,
                         {"evidence_id": evidence.evidence_id, "kind": evidence.kind, "score": evidence.score})
            return saved
        return self._idempotent("add_evidence", idempotency_key, mutate)

    def submit_assessment(self, sprint_id: str, result: AssessmentResult,
                          idempotency_key: str | None = None) -> SkillSprint:
        def mutate() -> SkillSprint:
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
            saved = self._save(sprint)
            self._event("assessment.completed", saved, idempotency_key,
                         {"passed": result.passed, "feedback": result.feedback})
            if result.passed:
                self._event("capability.verified", saved, idempotency_key,
                             {"skill_id": saved.skill_id, "version": saved.version})
            return saved
        return self._idempotent("submit_assessment", idempotency_key, mutate)

    def retry(self, sprint_id: str, idempotency_key: str | None = None) -> SkillSprint:
        def mutate() -> SkillSprint:
            sprint = self._load(sprint_id)
            sprint.state = transition(sprint.state, "retry")
            saved = self._save(sprint)
            self._event("sprint.retry", saved, idempotency_key)
            return saved
        return self._idempotent("retry", idempotency_key, mutate)

    def start_from_capability_gap(self, gap: dict[str, Any], idempotency_key: str | None = None) -> SkillSprint:
        """Create a sprint directly from a TANIA capability-gap contract."""
        learner_id = str(gap.get("learner_id") or gap.get("talent_id") or "")
        skill_id = str(gap.get("required_skill_id") or gap.get("skill_id") or "")
        if not learner_id or not skill_id:
            raise ValueError("TANIA capability gap requires learner_id and required_skill_id")
        source = {
            "system": "TANIA",
            "gap_id": gap.get("gap_id"),
            "capability_id": gap.get("capability_id"),
            "priority": gap.get("priority"),
        }
        return self.start_sprint(skill_id, learner_id, idempotency_key=idempotency_key, source=source)

    def audit(self, sprint_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if self.repository:
            try:
                return self.repository.list_events(sprint_id, limit)
            except (AttributeError, NotImplementedError):
                pass
        events = [e for e in self.events if sprint_id is None or e.get("sprint_id") == sprint_id]
        return events[-max(1, min(int(limit), 1000)):]

    def get(self, sprint_id: str) -> SkillSprint:
        return self._load(sprint_id)

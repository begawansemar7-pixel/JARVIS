from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable
from uuid import uuid4

from .models import Evidence, SkillDefinition, SkillSprint
from .planner import SprintStep


@dataclass
class SkillExecutionStep:
    step: int
    phase: str
    hours: float
    objective: str
    practice: str
    evidence: str
    action_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    output: str = ""
    evidence_id: str | None = None


@dataclass
class SkillExecutionPlan:
    plan_id: str
    sprint_id: str
    skill_id: str
    learner_id: str
    steps: list[SkillExecutionStep]
    status: str = "ready"

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "sprint_id": self.sprint_id,
            "skill_id": self.skill_id,
            "learner_id": self.learner_id,
            "status": self.status,
            "steps": [asdict(step) for step in self.steps],
        }


class SkillExecutionEngine:
    """Turn planner output into actual JARVIS action calls.

    The executor is deliberately conservative: every planner step is converted
    into an allowlisted action call, execution result is captured as evidence,
    and sprint hours are advanced only after successful action execution.
    """

    DEFAULT_ACTION = "skill_step_executor"

    def __init__(self, dispatcher: Callable[[str, dict[str, Any]], str],
                 runtime, action_allowlist: set[str] | None = None):
        self.dispatcher = dispatcher
        self.runtime = runtime
        self.action_allowlist = action_allowlist or {self.DEFAULT_ACTION}

    def build_plan(self, skill: SkillDefinition, sprint: SkillSprint,
                   steps: list[SprintStep]) -> SkillExecutionPlan:
        executable: list[SkillExecutionStep] = []
        for item in steps:
            action_name = getattr(item, "action_name", None) or self.DEFAULT_ACTION
            if action_name not in self.action_allowlist:
                raise ValueError(f"Planner action '{action_name}' is not allowlisted")
            params = getattr(item, "parameters", None) or {}
            params = {
                **params,
                "skill_id": skill.skill_id,
                "skill_name": skill.name,
                "phase": item.phase,
                "objective": item.objective,
                "practice": item.practice,
                "expected_evidence": item.evidence,
            }
            executable.append(SkillExecutionStep(
                item.step, item.phase, item.hours, item.objective, item.practice,
                item.evidence, action_name, params,
            ))
        return SkillExecutionPlan(uuid4().hex, sprint.sprint_id, skill.skill_id,
                                  sprint.learner_id, executable)

    def execute(self, plan: SkillExecutionPlan, *, idempotency_prefix: str | None = None) -> SkillExecutionPlan:
        plan.status = "running"
        for step in plan.steps:
            if step.status == "completed":
                continue
            key = f"{idempotency_prefix}:step:{step.step}" if idempotency_prefix else None
            try:
                output = self.dispatcher(step.action_name, step.parameters)
                if not output or str(output).startswith("Tool '") or "failed:" in str(output).lower():
                    raise RuntimeError(str(output or "Action returned no output"))
                step.output = str(output)
                step.status = "completed"
                evidence = Evidence(
                    uuid4().hex,
                    f"execution:{step.phase}",
                    f"Step {step.step}: {step.objective}",
                    100.0,
                    {"plan_id": plan.plan_id, "action_name": step.action_name,
                     "phase": step.phase, "output": step.output[:4000]},
                )
                self.runtime.add_evidence(plan.sprint_id, evidence, idempotency_key=key)
                step.evidence_id = evidence.evidence_id
                self.runtime.log_practice(plan.sprint_id, step.hours,
                                          idempotency_key=f"{key}:hours" if key else None)
            except Exception as exc:
                step.status = "failed"
                step.output = str(exc)
                plan.status = "failed"
                return plan
        plan.status = "completed"
        return plan

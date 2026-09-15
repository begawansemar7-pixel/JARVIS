"""JARVIS Skill Runtime action.

Bridge between Gemini Live tool-calling and the capability engine. SkillRuntime
remains authoritative for lifecycle, prerequisites, verification, execution,
audit and TANIA synchronization.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from core.skill_runtime.execution import SkillExecutionEngine
from core.skill_runtime.models import AssessmentResult, Evidence
from core.skill_runtime.planner import Adaptive20HourPlanner
from core.skill_runtime.repository import SQLiteSkillRepository, sprint_to_dict
from core.skill_runtime.service import SkillRuntime
from skill_registry.loader import load_registry

_BASE = Path(__file__).resolve().parent.parent
_REGISTRY = load_registry(_BASE / "skill-registry" / "skills")
_REPOSITORY = SQLiteSkillRepository(os.getenv("JARVIS_SKILL_DB", str(_BASE / "data" / "jarvis_skills.db")))
_RUNTIME = SkillRuntime(_REGISTRY, _REPOSITORY)
_PLANNER = Adaptive20HourPlanner(os.getenv("JARVIS_PLANNER_MODEL", "gemini-3.1-flash-preview"))


def _skill_step_dispatch(action_name: str, parameters: dict) -> str:
    if action_name != "skill_step_executor":
        raise ValueError(f"Unsupported skill action: {action_name}")
    from actions.skill_step_executor import _execute
    return _execute(parameters)


_EXECUTOR = SkillExecutionEngine(_skill_step_dispatch, _RUNTIME, {"skill_step_executor"})


def _result(operation: str, data) -> str:
    return json.dumps({"ok": True, "operation": operation, "data": data}, ensure_ascii=False, default=str)


def _handle(parameters: dict) -> str:
    operation = str(parameters.get("operation", "status")).lower()
    skill_id = parameters.get("skill_id")
    learner_id = parameters.get("learner_id", "default")
    sprint_id = parameters.get("sprint_id")
    idempotency_key = parameters.get("idempotency_key")

    if operation == "catalog":
        return _result(operation, [{"skill_id": s.skill_id, "name": s.name, "domain": s.domain,
                                    "level": s.level, "target_hours": s.target_hours, "prerequisites": s.prerequisites}
                                   for s in _REGISTRY.values()])

    if operation == "start":
        if not skill_id:
            raise ValueError("skill_id is required for start")
        return _result(operation, sprint_to_dict(_RUNTIME.start_sprint(skill_id, learner_id, idempotency_key=idempotency_key)))

    if operation == "tania_gap":
        gap = parameters.get("capability_gap") or {
            "gap_id": parameters.get("gap_id"), "learner_id": parameters.get("learner_id"),
            "talent_id": parameters.get("talent_id"), "capability_id": parameters.get("capability_id"),
            "required_skill_id": parameters.get("required_skill_id") or skill_id, "priority": parameters.get("priority"),
        }
        sprint = _RUNTIME.start_from_capability_gap(gap, idempotency_key=idempotency_key)
        return _result(operation, {"gap_id": gap.get("gap_id"), "capability_id": gap.get("capability_id"), "sprint": sprint_to_dict(sprint)})

    if operation in {"plan", "execute"}:
        if not sprint_id:
            raise ValueError(f"sprint_id is required for {operation}")
        sprint = _RUNTIME.get(sprint_id)
        skill = _REGISTRY[sprint.skill_id]
        steps = _PLANNER.plan(skill, sprint, parameters.get("learner_context") or {})
        plan = _EXECUTOR.build_plan(skill, sprint, steps)
        if operation == "plan":
            return _result(operation, plan.to_dict())
        _RUNTIME.record_event("skill.execution.started", sprint, {"plan_id": plan.plan_id, "step_count": len(plan.steps)})
        result = _EXECUTOR.execute(plan, idempotency_prefix=idempotency_key or plan.plan_id)
        _RUNTIME.record_event("skill.execution.completed" if result.status == "completed" else "skill.execution.failed",
                              sprint, {"plan_id": plan.plan_id, "status": result.status})
        return _result(operation, result.to_dict())

    if operation == "practice":
        if not sprint_id:
            raise ValueError("sprint_id is required for practice")
        if parameters.get("begin"):
            begin_key = f"{idempotency_key}:begin" if idempotency_key else None
            _RUNTIME.begin_practice(sprint_id, idempotency_key=begin_key)
        if parameters.get("hours") is not None:
            hours_key = f"{idempotency_key}:hours" if idempotency_key else None
            sprint = _RUNTIME.log_practice(sprint_id, float(parameters["hours"]), idempotency_key=hours_key)
        else:
            sprint = _RUNTIME.get(sprint_id)
        return _result(operation, sprint_to_dict(sprint))

    if operation == "evidence":
        if not sprint_id:
            raise ValueError("sprint_id is required for evidence")
        for key in ("kind", "title"):
            if not parameters.get(key):
                raise ValueError(f"{key} is required for evidence")
        evidence = Evidence(parameters.get("evidence_id", uuid4().hex), parameters["kind"], parameters["title"],
                             float(parameters.get("score", 0)), parameters.get("metadata") or {})
        return _result(operation, sprint_to_dict(_RUNTIME.add_evidence(sprint_id, evidence, idempotency_key)))

    if operation == "assess":
        if not sprint_id:
            raise ValueError("sprint_id is required for assess")
        required = ("knowledge", "execution", "quality", "independence", "business_relevance", "evidence_score")
        missing = [key for key in required if key not in parameters]
        if missing:
            raise ValueError(f"Missing assessment fields: {', '.join(missing)}")
        result = AssessmentResult(float(parameters["knowledge"]), float(parameters["execution"]), float(parameters["quality"]),
                                  float(parameters["independence"]), float(parameters["business_relevance"]),
                                  float(parameters["evidence_score"]), feedback=parameters.get("feedback", ""))
        return _result(operation, sprint_to_dict(_RUNTIME.submit_assessment(sprint_id, result, idempotency_key)))

    if operation == "retry":
        if not sprint_id:
            raise ValueError("sprint_id is required for retry")
        return _result(operation, sprint_to_dict(_RUNTIME.retry(sprint_id, idempotency_key)))

    if operation == "audit":
        return _result(operation, _RUNTIME.audit(sprint_id, int(parameters.get("limit", 100))))

    if operation == "status":
        if sprint_id:
            return _result(operation, sprint_to_dict(_RUNTIME.get(sprint_id)))
        return _result(operation, [sprint_to_dict(s) for s in _REPOSITORY.list_sprints(learner_id)])

    raise ValueError(f"Unknown skill runtime operation: {operation}")


TOOL = {
    "name": "skill_runtime",
    "description": "Execute JARVIS skills and 20-hour capability sprints. Operations: catalog, start, tania_gap, plan, execute, practice, evidence, assess, retry, audit, status.",
    "parameters": {"type": "OBJECT", "properties": {
        "operation": {"type": "STRING", "description": "catalog|start|tania_gap|plan|execute|practice|evidence|assess|retry|audit|status"},
        "skill_id": {"type": "STRING", "description": "Registered skill ID"}, "learner_id": {"type": "STRING", "description": "Learner/talent identifier"},
        "sprint_id": {"type": "STRING", "description": "Sprint identifier"}, "idempotency_key": {"type": "STRING", "description": "Stable retry key"},
        "gap_id": {"type": "STRING", "description": "TANIA capability gap identifier"}, "talent_id": {"type": "STRING", "description": "TANIA talent identifier"},
        "capability_id": {"type": "STRING", "description": "TANIA capability identifier"}, "required_skill_id": {"type": "STRING", "description": "Skill mapped from TANIA gap"},
        "priority": {"type": "STRING", "description": "TANIA gap priority"}, "capability_gap": {"type": "OBJECT", "description": "TANIA capability-gap contract"},
        "begin": {"type": "BOOLEAN", "description": "Begin practice"}, "hours": {"type": "NUMBER", "description": "Practice hours"},
        "kind": {"type": "STRING", "description": "Evidence type"}, "title": {"type": "STRING", "description": "Evidence title"},
        "score": {"type": "NUMBER", "description": "Evidence score 0-100"}, "evidence_id": {"type": "STRING", "description": "Evidence ID"},
        "metadata": {"type": "OBJECT", "description": "Evidence metadata"}, "learner_context": {"type": "OBJECT", "description": "Planner context"},
        "knowledge": {"type": "NUMBER", "description": "Assessment score"}, "execution": {"type": "NUMBER", "description": "Assessment score"},
        "quality": {"type": "NUMBER", "description": "Assessment score"}, "independence": {"type": "NUMBER", "description": "Assessment score"},
        "business_relevance": {"type": "NUMBER", "description": "Business relevance score"}, "evidence_score": {"type": "NUMBER", "description": "Evidence gate score"},
        "feedback": {"type": "STRING", "description": "Assessment feedback"}, "limit": {"type": "INTEGER", "description": "Audit event limit"},
    }, "required": ["operation"]},
    "handler": _handle,
}

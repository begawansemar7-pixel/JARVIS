"""JARVIS Skill Runtime action.

Bridge between Gemini Live tool-calling and the capability engine. The action
is intentionally thin: SkillRuntime remains the authority for lifecycle,
evidence and verification, while this module translates tool parameters into
runtime calls and JSON-safe responses.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

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


def _result(operation: str, data) -> str:
    return json.dumps({"ok": True, "operation": operation, "data": data}, ensure_ascii=False, default=str)


def _handle(parameters: dict) -> str:
    operation = str(parameters.get("operation", "status")).lower()
    skill_id = parameters.get("skill_id")
    learner_id = parameters.get("learner_id", "default")
    sprint_id = parameters.get("sprint_id")

    if operation == "catalog":
        return _result(operation, [{
            "skill_id": s.skill_id, "name": s.name, "domain": s.domain,
            "level": s.level, "target_hours": s.target_hours,
            "prerequisites": s.prerequisites,
        } for s in _REGISTRY.values()])

    if operation == "start":
        if not skill_id:
            raise ValueError("skill_id is required for start")
        sprint = _RUNTIME.start_sprint(skill_id, learner_id)
        return _result(operation, sprint_to_dict(sprint))

    if operation == "practice":
        if not sprint_id:
            raise ValueError("sprint_id is required for practice")
        sprint = _RUNTIME.begin_practice(sprint_id) if parameters.get("begin") else _RUNTIME.get(sprint_id)
        if parameters.get("hours") is not None:
            sprint = _RUNTIME.log_practice(sprint_id, float(parameters["hours"]))
        return _result(operation, sprint_to_dict(sprint))

    if operation == "evidence":
        if not sprint_id:
            raise ValueError("sprint_id is required for evidence")
        for key in ("kind", "title"):
            if not parameters.get(key):
                raise ValueError(f"{key} is required for evidence")
        evidence = Evidence(
            parameters.get("evidence_id", uuid4().hex),
            parameters["kind"], parameters["title"],
            float(parameters.get("score", 0)), parameters.get("metadata") or {},
        )
        return _result(operation, sprint_to_dict(_RUNTIME.add_evidence(sprint_id, evidence)))

    if operation == "plan":
        if not sprint_id:
            raise ValueError("sprint_id is required for plan")
        sprint = _RUNTIME.get(sprint_id)
        skill = _REGISTRY[sprint.skill_id]
        steps = _PLANNER.plan(skill, sprint, parameters.get("learner_context") or {})
        return _result(operation, {
            "sprint_id": sprint_id,
            "remaining_hours": round(skill.target_hours - sprint.hours_completed, 2),
            "steps": [s.__dict__ for s in steps],
        })

    if operation == "assess":
        if not sprint_id:
            raise ValueError("sprint_id is required for assess")
        required = ("knowledge", "execution", "quality", "independence", "business_relevance", "evidence_score")
        missing = [key for key in required if key not in parameters]
        if missing:
            raise ValueError(f"Missing assessment fields: {', '.join(missing)}")
        result = AssessmentResult(
            knowledge=float(parameters["knowledge"]), execution=float(parameters["execution"]),
            quality=float(parameters["quality"]), independence=float(parameters["independence"]),
            business_relevance=float(parameters["business_relevance"]),
            evidence_score=float(parameters["evidence_score"]), feedback=parameters.get("feedback", ""),
        )
        return _result(operation, sprint_to_dict(_RUNTIME.submit_assessment(sprint_id, result)))

    if operation == "retry":
        if not sprint_id:
            raise ValueError("sprint_id is required for retry")
        return _result(operation, sprint_to_dict(_RUNTIME.retry(sprint_id)))

    if operation == "status":
        if sprint_id:
            return _result(operation, sprint_to_dict(_RUNTIME.get(sprint_id)))
        return _result(operation, [sprint_to_dict(s) for s in _REPOSITORY.list_sprints(learner_id)])

    raise ValueError(f"Unknown skill runtime operation: {operation}")


TOOL = {
    "name": "skill_runtime",
    "description": "Execute JARVIS skills and 20-hour capability sprints. Operations: catalog, start, plan, practice, evidence, assess, retry, status.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "operation": {"type": "STRING", "description": "catalog|start|plan|practice|evidence|assess|retry|status"},
            "skill_id": {"type": "STRING", "description": "Registered skill ID, e.g. AI-RAG-001"},
            "learner_id": {"type": "STRING", "description": "Learner/talent identifier"},
            "sprint_id": {"type": "STRING", "description": "Sprint identifier"},
            "begin": {"type": "BOOLEAN", "description": "Transition a sprint into practice"},
            "hours": {"type": "NUMBER", "description": "Focused practice hours to log"},
            "kind": {"type": "STRING", "description": "Evidence type"},
            "title": {"type": "STRING", "description": "Evidence title"},
            "score": {"type": "NUMBER", "description": "Evidence score 0-100"},
            "evidence_id": {"type": "STRING", "description": "Optional evidence ID"},
            "metadata": {"type": "OBJECT", "description": "Evidence metadata"},
            "learner_context": {"type": "OBJECT", "description": "Context used by adaptive planner"},
            "knowledge": {"type": "NUMBER", "description": "Assessment score 0-100"},
            "execution": {"type": "NUMBER", "description": "Assessment score 0-100"},
            "quality": {"type": "NUMBER", "description": "Assessment score 0-100"},
            "independence": {"type": "NUMBER", "description": "Assessment score 0-100"},
            "business_relevance": {"type": "NUMBER", "description": "Assessment score 0-100"},
            "evidence_score": {"type": "NUMBER", "description": "Evidence gate score 0-100"},
            "feedback": {"type": "STRING", "description": "Assessment feedback"},
        },
        "required": ["operation"],
    },
    "handler": _handle,
}

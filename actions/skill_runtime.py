"""JARVIS Skill Runtime action.

This is the bridge between Gemini Live tool-calling and the capability engine.
The action exposes one stable `skill_runtime` tool while keeping lifecycle/state
logic inside core.skill_runtime.
"""
from __future__ import annotations

import os
from pathlib import Path

from core.skill_runtime.planner import Adaptive20HourPlanner
from core.skill_runtime.repository import SQLiteSkillRepository, sprint_to_dict
from core.skill_runtime.service import SkillRuntime
from core.skill_runtime.models import AssessmentResult, Evidence
from skill_registry.loader import load_registry

_BASE = Path(__file__).resolve().parent.parent
_REGISTRY = load_registry(_BASE / "skill-registry" / "skills")
_REPOSITORY = SQLiteSkillRepository(os.getenv("JARVIS_SKILL_DB", str(_BASE / "data" / "jarvis_skills.db")))
_RUNTIME = SkillRuntime(_REGISTRY, _REPOSITORY)
_PLANNER = Adaptive20HourPlanner(os.getenv("JARVIS_PLANNER_MODEL", "gemini-3.1-flash-preview"))


def _handle(parameters: dict) -> str:
    operation = parameters.get("operation", "status")
    skill_id = parameters.get("skill_id")
    learner_id = parameters.get("learner_id", "default")
    sprint_id = parameters.get("sprint_id")

    if operation == "start":
        sprint = _RUNTIME.start_sprint(skill_id, learner_id)
        return f"Started {skill_id} sprint {sprint.sprint_id}; state={sprint.state}."
    if operation == "practice":
        sprint = _RUNTIME.begin_practice(sprint_id) if parameters.get("begin") else _RUNTIME.get(sprint_id)
        if parameters.get("hours"):
            sprint = _RUNTIME.log_practice(sprint_id, float(parameters["hours"]))
        return str(sprint_to_dict(sprint))
    if operation == "evidence":
        e = Evidence(parameters.get("evidence_id", __import__('uuid').uuid4().hex), parameters["kind"], parameters["title"], float(parameters.get("score", 0)), parameters.get("metadata", {}))
        return str(sprint_to_dict(_RUNTIME.add_evidence(sprint_id, e)))
    if operation == "plan":
        sprint = _RUNTIME.get(sprint_id)
        skill = _REGISTRY[sprint.skill_id]
        steps = _PLANNER.plan(skill, sprint, parameters.get("learner_context", {}))
        return str([s.__dict__ for s in steps])
    if operation == "assess":
        result = AssessmentResult(
            knowledge=float(parameters["knowledge"]), execution=float(parameters["execution"]),
            quality=float(parameters["quality"]), independence=float(parameters["independence"]),
            business_relevance=float(parameters["business_relevance"]), evidence_score=float(parameters["evidence_score"]),
            feedback=parameters.get("feedback", ""),
        )
        return str(sprint_to_dict(_RUNTIME.submit_assessment(sprint_id, result)))
    if operation == "retry":
        return str(sprint_to_dict(_RUNTIME.retry(sprint_id)))
    if operation == "status":
        return str(sprint_to_dict(_RUNTIME.get(sprint_id))) if sprint_id else str([sprint_to_dict(s) for s in _REPOSITORY.list_sprints(learner_id)])
    if operation == "catalog":
        return str([{"skill_id": s.skill_id, "name": s.name, "level": s.level, "target_hours": s.target_hours} for s in _REGISTRY.values()])
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

"""REST API for JARVIS Skill Runtime and Capability Execution Engine."""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from core.skill_runtime.execution import SkillExecutionEngine
from core.skill_runtime.models import AssessmentResult, Evidence
from core.skill_runtime.planner import Adaptive20HourPlanner
from core.skill_runtime.repository import SQLiteSkillRepository, SupabaseSkillRepository, sprint_to_dict
from core.skill_runtime.service import SkillRuntime
from skill_registry.loader import load_registry

BASE = Path(__file__).resolve().parent.parent
registry = load_registry(BASE / "skill-registry" / "skills")


def _build_repository():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if supabase_url and supabase_key:
        return SupabaseSkillRepository(supabase_url, supabase_key)
    return SQLiteSkillRepository(os.getenv("JARVIS_SKILL_DB", str(BASE / "data" / "jarvis_skills.db")))


repository = _build_repository()
runtime = SkillRuntime(registry, repository)
planner = Adaptive20HourPlanner(os.getenv("JARVIS_PLANNER_MODEL", "gemini-3.1-flash-preview"))


def _dispatch(action_name: str, parameters: dict) -> str:
    if action_name != "skill_step_executor":
        raise ValueError(f"Unsupported skill action: {action_name}")
    from actions.skill_step_executor import _execute
    return _execute(parameters)


executor = SkillExecutionEngine(_dispatch, runtime, {"skill_step_executor"})
app = FastAPI(title="JARVIS Capability Execution Engine API", version="1.3.0")


class StartRequest(BaseModel):
    learner_id: str = Field(default="default", min_length=1, max_length=128)


class PracticeRequest(BaseModel):
    hours: float = Field(gt=0, le=20)


class EvidenceRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    score: float = Field(ge=0, le=100)
    metadata: dict = Field(default_factory=dict)


class PlanRequest(BaseModel):
    learner_context: dict = Field(default_factory=dict)


class AssessmentRequest(BaseModel):
    knowledge: float = Field(ge=0, le=100)
    execution: float = Field(ge=0, le=100)
    quality: float = Field(ge=0, le=100)
    independence: float = Field(ge=0, le=100)
    business_relevance: float = Field(ge=0, le=100)
    evidence_score: float = Field(ge=0, le=100)
    feedback: str = ""


class CapabilityGapRequest(BaseModel):
    gap_id: str = Field(min_length=1, max_length=128)
    learner_id: str = Field(min_length=1, max_length=128)
    capability_id: str | None = Field(default=None, max_length=128)
    required_skill_id: str = Field(min_length=1, max_length=128)
    priority: str | None = Field(default=None, max_length=32)
    context: dict = Field(default_factory=dict)


@app.get("/health")
def health():
    return {"status": "ok", "service": "jarvis-capability-execution-engine", "skills": len(registry), "repository": type(repository).__name__}


@app.get("/skills")
def skills():
    return [{"skill_id": s.skill_id, "name": s.name, "domain": s.domain, "level": s.level,
             "target_hours": s.target_hours, "prerequisites": s.prerequisites} for s in registry.values()]


@app.post("/skills/{skill_id}/sprints")
def start(skill_id: str, body: StartRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    try:
        return sprint_to_dict(runtime.start_sprint(skill_id, body.learner_id, idempotency_key=idempotency_key))
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/tania/capability-gaps/{gap_id}/sprints")
def start_from_tania(gap_id: str, body: CapabilityGapRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if gap_id != body.gap_id:
        raise HTTPException(400, "gap_id path and body must match")
    try:
        gap = body.model_dump()
        sprint = runtime.start_from_capability_gap(gap, idempotency_key=idempotency_key or f"tania:{gap_id}")
        return {"source": "TANIA", "gap_id": gap_id, "capability_id": body.capability_id, "sprint": sprint_to_dict(sprint)}
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/sprints/{sprint_id}")
def get_sprint(sprint_id: str):
    try:
        return sprint_to_dict(runtime.get(sprint_id))
    except KeyError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/sprints/{sprint_id}/plan")
def plan(sprint_id: str, body: PlanRequest | None = None):
    try:
        sprint = runtime.get(sprint_id)
        skill = registry[sprint.skill_id]
        context = body.learner_context if body else {}
        return executor.build_plan(skill, sprint, planner.plan(skill, sprint, context)).to_dict()
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/sprints/{sprint_id}/execute")
def execute(sprint_id: str, body: PlanRequest | None = None,
            idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    try:
        sprint = runtime.get(sprint_id)
        skill = registry[sprint.skill_id]
        plan = executor.build_plan(skill, sprint, planner.plan(skill, sprint, body.learner_context if body else {}))
        runtime.record_event("skill.execution.started", sprint, {"plan_id": plan.plan_id, "step_count": len(plan.steps)})
        result = executor.execute(plan, idempotency_prefix=idempotency_key or plan.plan_id)
        runtime.record_event("skill.execution.completed" if result.status == "completed" else "skill.execution.failed",
                             sprint, {"plan_id": plan.plan_id, "status": result.status})
        return result.to_dict()
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/sprints/{sprint_id}/practice/start")
def begin_practice(sprint_id: str, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    try:
        return sprint_to_dict(runtime.begin_practice(sprint_id, idempotency_key=idempotency_key))
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/sprints/{sprint_id}/practice")
def practice(sprint_id: str, body: PracticeRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    try:
        return sprint_to_dict(runtime.log_practice(sprint_id, body.hours, idempotency_key=idempotency_key))
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/sprints/{sprint_id}/evidence")
def evidence(sprint_id: str, body: EvidenceRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    try:
        evidence_item = Evidence(uuid4().hex, body.kind, body.title, body.score, body.metadata)
        return sprint_to_dict(runtime.add_evidence(sprint_id, evidence_item, idempotency_key=idempotency_key))
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/sprints/{sprint_id}/assessment")
def assessment(sprint_id: str, body: AssessmentRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    try:
        result = AssessmentResult(**body.model_dump())
        return sprint_to_dict(runtime.submit_assessment(sprint_id, result, idempotency_key=idempotency_key))
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/sprints/{sprint_id}/retry")
def retry(sprint_id: str, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    try:
        return sprint_to_dict(runtime.retry(sprint_id, idempotency_key=idempotency_key))
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/sprints/{sprint_id}/audit")
def audit(sprint_id: str, limit: int = 100):
    try:
        runtime.get(sprint_id)
        return runtime.audit(sprint_id, limit)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e

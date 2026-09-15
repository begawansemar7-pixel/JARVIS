"""REST API for JARVIS Skill Runtime.

Run standalone with: uvicorn api.skill_api:app --host 0.0.0.0 --port 8787
"""
from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.skill_runtime.models import AssessmentResult, Evidence
from core.skill_runtime.repository import SQLiteSkillRepository, sprint_to_dict
from core.skill_runtime.service import SkillRuntime
from core.skill_runtime.planner import Adaptive20HourPlanner
from skill_registry.loader import load_registry

BASE = Path(__file__).resolve().parent.parent
registry = load_registry(BASE / "skill-registry" / "skills")
repository = SQLiteSkillRepository(os.getenv("JARVIS_SKILL_DB", str(BASE / "data" / "jarvis_skills.db")))
runtime = SkillRuntime(registry, repository)
planner = Adaptive20HourPlanner(os.getenv("JARVIS_PLANNER_MODEL", "gemini-3.1-flash-preview"))
app = FastAPI(title="JARVIS Skill Runtime API", version="1.0.0")


class StartRequest(BaseModel):
    learner_id: str = "default"

class PracticeRequest(BaseModel):
    hours: float = Field(gt=0, le=20)

class EvidenceRequest(BaseModel):
    kind: str
    title: str
    score: float = Field(ge=0, le=100)
    metadata: dict = {}

class AssessmentRequest(BaseModel):
    knowledge: float = Field(ge=0, le=100)
    execution: float = Field(ge=0, le=100)
    quality: float = Field(ge=0, le=100)
    independence: float = Field(ge=0, le=100)
    business_relevance: float = Field(ge=0, le=100)
    evidence_score: float = Field(ge=0, le=100)
    feedback: str = ""


@app.get("/health")
def health():
    return {"status": "ok", "service": "jarvis-skill-runtime", "skills": len(registry)}

@app.get("/skills")
def skills():
    return [{"skill_id": s.skill_id, "name": s.name, "domain": s.domain, "level": s.level,
             "target_hours": s.target_hours, "prerequisites": s.prerequisites} for s in registry.values()]

@app.post("/skills/{skill_id}/sprints")
def start(skill_id: str, body: StartRequest):
    try:
        return sprint_to_dict(runtime.start_sprint(skill_id, body.learner_id))
    except (KeyError, ValueError) as e:
        raise HTTPException(404, str(e))

@app.get("/sprints/{sprint_id}")
def get_sprint(sprint_id: str):
    try:
        return sprint_to_dict(runtime.get(sprint_id))
    except KeyError as e:
        raise HTTPException(404, str(e))

@app.post("/sprints/{sprint_id}/practice/start")
def begin_practice(sprint_id: str):
    try:
        return sprint_to_dict(runtime.begin_practice(sprint_id))
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))

@app.post("/sprints/{sprint_id}/practice")
def practice(sprint_id: str, body: PracticeRequest):
    try:
        return sprint_to_dict(runtime.log_practice(sprint_id, body.hours))
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))

@app.post("/sprints/{sprint_id}/evidence")
def evidence(sprint_id: str, body: EvidenceRequest):
    try:
        e = Evidence(__import__('uuid').uuid4().hex, body.kind, body.title, body.score, body.metadata)
        return sprint_to_dict(runtime.add_evidence(sprint_id, e))
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))

@app.post("/sprints/{sprint_id}/plan")
def plan(sprint_id: str, learner_context: dict = {}):
    try:
        sprint = runtime.get(sprint_id)
        return {"sprint_id": sprint_id, "steps": [s.__dict__ for s in planner.plan(registry[sprint.skill_id], sprint, learner_context)]}
    except KeyError as e:
        raise HTTPException(404, str(e))

@app.post("/sprints/{sprint_id}/assessment")
def assessment(sprint_id: str, body: AssessmentRequest):
    try:
        result = AssessmentResult(**body.model_dump())
        return sprint_to_dict(runtime.submit_assessment(sprint_id, result))
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))

@app.post("/sprints/{sprint_id}/retry")
def retry(sprint_id: str):
    try:
        return sprint_to_dict(runtime.retry(sprint_id))
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Any

from .models import SkillDefinition, SkillSprint


@dataclass
class SprintStep:
    step: int
    phase: str
    hours: float
    objective: str
    practice: str
    evidence: str


class Adaptive20HourPlanner:
    """LLM-assisted planner with a deterministic fallback.

    The LLM proposes a practical sequence; the runtime remains authoritative for
    state transitions, hours and assessment. This prevents an LLM from mutating
    capability state directly.
    """
    def __init__(self, model: str = "gemini-3.1-flash-preview"):
        self.model = model

    def plan(self, skill: SkillDefinition, sprint: SkillSprint, learner_context: dict[str, Any] | None = None) -> list[SprintStep]:
        remaining = max(0.0, skill.target_hours - sprint.hours_completed)
        if remaining <= 0:
            return []
        context = learner_context or {}
        try:
            return self._llm_plan(skill, sprint, context, remaining)
        except Exception:
            return self._fallback(skill, remaining)

    def _llm_plan(self, skill, sprint, context, remaining):
        from google import genai
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        prompt = f"""Create an adaptive rapid-skill-acquisition plan for JARVIS.
Skill: {skill.name} ({skill.skill_id})
Target performance: {skill.target_performance}
Remaining focused hours: {remaining}
Completed hours: {sprint.hours_completed}
Learner context: {context}
Return ONLY JSON array. Each item: step, phase, hours, objective, practice, evidence.
Use phases learn, practice, build, evaluate. Total hours must equal remaining.
Prioritize a concrete deliverable and fast feedback."""
        response = client.models.generate_content(model=self.model, contents=prompt)
        data = json.loads(response.text)
        steps = [SprintStep(int(x["step"]), x["phase"], float(x["hours"]), x["objective"], x["practice"], x["evidence"]) for x in data]
        total = round(sum(x.hours for x in steps), 2)
        if not steps or abs(total - remaining) > 0.05:
            raise ValueError("Planner returned an invalid hour budget")
        return steps

    @staticmethod
    def _fallback(skill, remaining):
        # A deterministic 20-hour sequence is always available offline.
        chunks = [min(2.0, remaining), min(6.0, max(0, remaining-2.0)), min(9.0, max(0, remaining-8.0)), max(0, remaining-17.0)]
        chunks = [round(x, 2) for x in chunks if x > 0]
        phases = [
            ("learn", "Learn the minimum concepts required to perform the target skill", "Study one focused reference and explain the architecture from memory", "notes + architecture"),
            ("practice", "Build small exercises against the target performance", "Implement and test one capability at a time", "working code + test output"),
            ("build", "Build a useful end-to-end prototype", "Integrate the components into a realistic use case", "prototype + demo"),
            ("evaluate", "Evaluate and close the highest-impact gaps", "Run rubric-based tests and fix failures", "evaluation report"),
        ]
        return [SprintStep(i+1, phases[i][0], h, phases[i][1], phases[i][2], phases[i][3]) for i, h in enumerate(chunks)]

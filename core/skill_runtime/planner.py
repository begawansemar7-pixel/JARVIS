from __future__ import annotations

import json
import os
from dataclasses import dataclass
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
    """LLM-assisted planner with deterministic fallback.

    The planner may propose learning work, but it cannot mutate sprint state.
    Runtime remains authoritative for hours, evidence, assessment and verification.
    """
    ALLOWED_PHASES = {"learn", "practice", "build", "evaluate"}

    def __init__(self, model: str = "gemini-3.1-flash-preview"):
        self.model = model

    def plan(self, skill: SkillDefinition, sprint: SkillSprint,
             learner_context: dict[str, Any] | None = None) -> list[SprintStep]:
        remaining = max(0.0, round(skill.target_hours - sprint.hours_completed, 2))
        if remaining <= 0:
            return []
        context = learner_context or {}
        try:
            return self._llm_plan(skill, sprint, context, remaining)
        except Exception:
            return self._fallback(skill, remaining)

    def _llm_plan(self, skill, sprint, context, remaining):
        from google import genai

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        client = genai.Client(api_key=api_key)
        prompt = f"""Create an adaptive rapid-skill-acquisition plan for JARVIS.
Skill: {skill.name} ({skill.skill_id})
Target performance: {skill.target_performance}
Remaining focused hours: {remaining}
Completed hours: {sprint.hours_completed}
Learner context: {context}
Return ONLY a JSON array. Each item must contain: step, phase, hours, objective, practice, evidence.
Allowed phases: learn, practice, build, evaluate.
Total planned hours must equal remaining. Use positive hours only and prioritize a concrete deliverable and fast feedback."""
        response = client.models.generate_content(model=self.model, contents=prompt)
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].lstrip()
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("Planner response must be a JSON array")

        steps: list[SprintStep] = []
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                raise ValueError("Planner step must be an object")
            phase = str(item["phase"]).lower().strip()
            hours = float(item["hours"])
            if phase not in self.ALLOWED_PHASES or hours <= 0:
                raise ValueError("Planner returned invalid phase or hours")
            steps.append(SprintStep(
                int(item.get("step", index)), phase, round(hours, 2),
                str(item["objective"]), str(item["practice"]), str(item["evidence"]),
            ))

        total = round(sum(x.hours for x in steps), 2)
        if not steps or abs(total - remaining) > 0.05:
            raise ValueError("Planner returned an invalid hour budget")
        return steps

    @staticmethod
    def _fallback(skill, remaining):
        chunks = [
            min(2.0, remaining),
            min(6.0, max(0, remaining - 2.0)),
            min(9.0, max(0, remaining - 8.0)),
            max(0, remaining - 17.0),
        ]
        chunks = [round(x, 2) for x in chunks if x > 0]
        phases = [
            ("learn", "Learn the minimum concepts required to perform the target skill", "Study one focused reference and explain the architecture from memory", "notes + architecture"),
            ("practice", "Build small exercises against the target performance", "Implement and test one capability at a time", "working code + test output"),
            ("build", "Build a useful end-to-end prototype", "Integrate the components into a realistic use case", "prototype + demo"),
            ("evaluate", "Evaluate and close the highest-impact gaps", "Run rubric-based tests and fix failures", "evaluation report"),
        ]
        return [SprintStep(i + 1, phases[i][0], h, phases[i][1], phases[i][2], phases[i][3])
                for i, h in enumerate(chunks)]

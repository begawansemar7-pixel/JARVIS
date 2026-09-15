"""Generic bounded executor used by SkillExecutionPlan.

This action turns a concrete skill objective into an executable JARVIS tool call.
It is intentionally narrow: it performs one step, returns a verifiable result,
and does not mutate SkillRuntime state itself.
"""
from __future__ import annotations

import json
import os


def _execute(parameters: dict) -> str:
    objective = str(parameters.get("objective", "")).strip()
    practice = str(parameters.get("practice", "")).strip()
    skill_name = str(parameters.get("skill_name", "")).strip()
    phase = str(parameters.get("phase", "practice")).strip()
    if not objective:
        raise ValueError("objective is required")

    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    client = genai.Client(api_key=api_key)
    prompt = f"""You are JARVIS executing one bounded skill-acquisition step.
Skill: {skill_name}
Phase: {phase}
Objective: {objective}
Practice instruction: {practice}
Expected evidence: {parameters.get('expected_evidence', '')}

Execute the step as far as possible using available reasoning and tools.
Return ONLY valid JSON with:
{{
  "success": true,
  "result": "concise result",
  "deliverable": "what was produced or verified",
  "next_action": "one concrete next action or empty string"
}}
Do not claim that an external action, file change, deployment, test, or observation occurred unless it actually occurred in this execution context."""
    response = client.models.generate_content(
        model=os.getenv("JARVIS_SKILL_EXECUTOR_MODEL", "gemini-3.1-flash-preview"),
        contents=prompt,
    )
    text = (response.text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    data = json.loads(text)
    if not isinstance(data, dict) or data.get("success") is not True:
        raise RuntimeError(f"Skill step did not succeed: {data}")
    return json.dumps(data, ensure_ascii=False)


TOOL = {
    "name": "skill_step_executor",
    "description": "Execute one bounded JARVIS skill-learning step and return a verifiable result.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "skill_id": {"type": "STRING"},
            "skill_name": {"type": "STRING"},
            "phase": {"type": "STRING"},
            "objective": {"type": "STRING"},
            "practice": {"type": "STRING"},
            "expected_evidence": {"type": "STRING"},
        },
        "required": ["objective"],
    },
    "handler": _execute,
}

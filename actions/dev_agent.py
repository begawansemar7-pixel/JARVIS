"""JARVIS Software Engineering action.

The public action contract remains ``dev_agent`` so existing routing stays
compatible. The implementation delegates to the JARVIS-native SWE subsystem,
which adds repository intelligence, durable engineering sessions, model routing,
verification/repair loops and self-development guardrails.
"""
from __future__ import annotations

from engineering.swe_agent import run as _run_swe


def dev_agent(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    """Run a governed JARVIS SWE task."""
    return _run_swe(parameters or {}, player=player, speak=speak)


TOOL = {
    "name": "dev_agent",
    "description": (
        "JARVIS Software Engineering Agent. Inspects a repository, builds a compact code map, "
        "plans changes, writes code, runs verification, repairs failures, records an engineering "
        "session, and supports plan/review/test/build modes. JARVIS repository self-modification is "
        "blocked unless explicitly authorized by JARVIS_SWE_ALLOW_REPO_WRITE=1."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "description": {
                "type": "STRING",
                "description": "Software requirement, bug, feature or engineering objective"
            },
            "language": {
                "type": "STRING",
                "description": "Primary programming language (default: python)"
            },
            "project_name": {
                "type": "STRING",
                "description": "Desktop project folder name when repo_path is omitted"
            },
            "repo_path": {
                "type": "STRING",
                "description": "Existing repository/project root to inspect or modify"
            },
            "mode": {
                "type": "STRING",
                "description": "plan | review | build | test; build is the default"
            },
            "timeout": {
                "type": "INTEGER",
                "description": "Verification command timeout in seconds (5-600)"
            }
        },
        "required": ["description"]
    },
    "handler": dev_agent,
}

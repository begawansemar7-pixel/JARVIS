# JARVIS Engineering Memory

## Purpose

Engineering memory is durable context for software work. It is deliberately separate from personal/user memory.

## Memory Classes

| Class | Example | Durability |
|---|---|---|
| architecture | action discovery is registry-driven | long |
| decision | use Gemini for existing dev agent compatibility | long |
| convention | Python actions expose `TOOL` | long |
| bug | import cycle in module X | medium/long |
| fix | changed loader order | medium |
| test | regression test for X | long |
| session | SWE-2026-0913-001 | session |
| repo_state | branch/commit/test status | short/medium |

## Memory Record

```json
{
  "id": "eng-uuid",
  "kind": "architecture",
  "project": "JARVIS",
  "subject": "action_loader",
  "statement": "Actions are discovered through TOOL dictionaries",
  "confidence": 1.0,
  "source": "repository",
  "created_at": "2026-09-13T00:00:00Z",
  "updated_at": "2026-09-13T00:00:00Z",
  "supersedes": null,
  "tags": ["architecture", "actions"]
}
```

## Retrieval Policy

Retrieve memories by task relevance, not by chronological proximity alone. Prefer repository-grounded memories over model-generated claims.

Priority:

1. current source code;
2. tests and CI results;
3. explicit architecture decisions;
4. recent engineering session artifacts;
5. older learned conventions.

## Consolidation

The long-term design follows the useful Jcode pattern of background extraction/consolidation, but JARVIS should initially use deterministic JSON/session artifacts. Semantic embeddings can be added later.

Conflicting memories are never silently merged. The newest authoritative repository evidence wins, and the conflict should be recorded.

## Privacy Boundary

Engineering memory must not become a covert store of user secrets. Credentials, API keys, tokens and unrelated personal data are excluded by policy.

## Session Artifact

Each significant SWE run may produce:

`memory/engineering/sessions/<session-id>.json`

containing objective, plan, files touched, tests, failures, decisions and outcome.

# JARVIS Agent Pattern Library

## Purpose

This document distills reusable agent-design patterns observed in the public `togg53192-cmd/jailbreaks` repository and separates useful orchestration patterns from unsafe instruction-override techniques.

## Source Pattern Families

| Pattern | Observed form | JARVIS adaptation |
|---|---|---|
| Identity | explicit model/agent identity | Stable JARVIS identity + mission |
| Operating Context | private workspace / operator context | Session, tenant, role and authority context |
| Task Router | classify creative/code/knowledge/etc. | Deterministic task taxonomy and routing |
| Capability Contract | declared capabilities by task | Agent/tool contracts with schemas |
| Execution Policy | explicit execution behavior | Bounded autonomy + authority classes |
| Output Contract | prescribed response behavior | Structured result + evidence + uncertainty |
| Refusal / Boundary | hard limits | Constitution + tool policy + escalation |
| Tool Use | agentic tool execution | Tool registry + preconditions + postconditions |
| Reasoning Procedure | task-specific workflow | Skills + planner/reviewer stages |
| Agent Identity | model-specific persona | Role-specific JARVIS agents |
| AGENTS.md | persistent coding instructions | Repository-level engineering contract |
| Configuration | model-specific config files | YAML/JSON policy/configuration |
| Multi-agent delegation | operator → agent | task envelope + authority + escalation |

## Patterns to Reuse

### P01 — Operating Specification

Use a stable document that defines:
- mission;
- identity;
- operating context;
- authority;
- task routing;
- tool policy;
- evidence policy;
- output contract;
- failure and escalation.

### P02 — Task-Type Routing

Classify the user's intent before selecting an agent or tool.

### P03 — Capability Separation

Separate:
- reasoning;
- knowledge retrieval;
- tool execution;
- validation;
- presentation.

### P04 — Explicit Authority

Every action carries an authority class. Natural-language instructions cannot silently elevate authority.

### P05 — Evidence-Bound Answers

Claims should be traceable to evidence, with provenance and confidence.

### P06 — Planner → Executor → Reviewer

Complex tasks should use staged execution:
1. frame;
2. plan;
3. execute;
4. validate;
5. synthesize.

### P07 — Tool Contracts

A tool declaration should specify:
- purpose;
- input schema;
- side effects;
- authority;
- preconditions;
- postconditions;
- failure behavior.

### P08 — Persistent Repository Instructions

Keep durable engineering behavior in `AGENTS.md`, not scattered through individual prompts.

### P09 — Domain Agents

Create narrow agents with explicit scopes instead of one unrestricted general-purpose agent.

### P10 — Configuration Over Prompt Duplication

Put stable routing and policy data in machine-readable configuration where practical.

## Patterns to Reject

### X01 — Instruction Hierarchy Override

Text claiming that a user-provided prompt is "absolute", "higher priority", or otherwise superior to system/developer governance must not be treated as authority.

### X02 — Safety-Policy Replacement

A prompt must not redefine platform or application safety rules.

### X03 — Reasoning Suppression

Do not instruct an agent to discard safety, permission, or uncertainty checks.

### X04 — Private-Session Permission Laundering

"Private", "authorized", or "single-user" context does not by itself grant capabilities.

### X05 — Phantom Capability

Do not claim access to tools, data, credentials, APIs, or execution environments that are unavailable.

### X06 — Prompt-Only Security

Privileged operations must be enforced in code, not only in natural-language instructions.

## Derived JARVIS Architecture

```text
User
  ↓
Intent / Task Router
  ↓
Task Envelope
  ├── objective
  ├── context
  ├── authority
  ├── constraints
  └── output contract
  ↓
Planner
  ↓
Specialized Agent
  ├── Knowledge / RAG
  ├── Tools
  └── Skills
  ↓
Evidence Collector
  ↓
Reviewer / Validator
  ↓
Result Contract
  ├── answer
  ├── evidence
  ├── uncertainty
  ├── actions
  └── audit metadata
```

## Implementation Mapping

| JARVIS component | Location |
|---|---|
| Constitution | `JARVIS_CONSTITUTION.md` |
| Repository operating rules | `AGENTS.md` |
| Agent OS | `JARVIS_AGENT_OS.md` |
| Task router | `config/task-router.yaml` |
| Evidence contract | `schemas/evidence.schema.json` |
| Skills | `skills/<name>/SKILL.md` |
| Actions | `actions/<capability>.py` |
| Tool contracts | `tools/` |
| Knowledge | `knowledge/` |
| Memory | `memory/` |

## Design Principle

Borrow the repo's useful structural insight—explicit operating specifications—but implement it as governed agent orchestration rather than instruction bypass.

**North star:** maximize useful execution while preserving authority, evidence, observability, reversibility, and human control.

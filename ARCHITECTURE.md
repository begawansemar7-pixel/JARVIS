# JARVIS Technical Architecture

> **Status:** Architecture baseline v1.0  
> **Purpose:** Define the technical architecture, boundaries, interfaces, and evolution path of JARVIS.

## 1. Architectural Intent

JARVIS is a multimodal, tool-using AI agent designed to evolve from a desktop personal assistant into an **AI Employee and Company OS**.

The architecture separates five concerns:

1. **Perception** — voice, text, screen, camera and external information.
2. **Reasoning** — LLM-driven interpretation, planning and decision support.
3. **Memory** — durable user/project context and session continuity.
4. **Action** — deterministic execution through tools, actions and plugins.
5. **Governance** — permissions, confirmation, reversibility, auditability and policy.

The primary design rule is:

> **The model decides what should happen; governed tools determine what actually happens.**

## 2. System Context

```text
                         ┌─────────────────────────┐
                         │       HUMAN / CEO        │
                         │ voice · text · dashboard │
                         └────────────┬────────────┘
                                      │ intent
                                      ▼
┌──────────────────────────────────────────────────────────────────┐
│                         JARVIS RUNTIME                            │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────────┐  │
│  │ Perception   │──▶│ Orchestrator │──▶│ Reasoning / LLM     │  │
│  │ voice/vision │   │ session loop │   │ Gemini Live          │  │
│  └──────────────┘   └──────┬───────┘   └──────────┬──────────┘  │
│                            │ tool calls             │            │
│                ┌───────────▼───────────────────────▼────────┐   │
│                │             Governance Layer               │   │
│                │ confirmation · policy · permissions · log  │   │
│                └───────────┬───────────────────────┬────────┘   │
│                            │                       │            │
│                 ┌──────────▼─────────┐   ┌────────▼─────────┐  │
│                 │ Action Registry    │   │ Memory Layer     │  │
│                 │ tools / plugins    │   │ long-term/session│  │
│                 └──────────┬─────────┘   └──────────────────┘  │
└────────────────────────────┼───────────────────────────────────┘
                             │
          ┌──────────────────┼───────────────────────┐
          ▼                  ▼                       ▼
   Computer / OS       Web / Browser          Enterprise APIs
   files / settings    research / search      future connectors

             ┌───────────────────────────────────┐
             │ Skills / Decision Intelligence     │
             │ CEO · strategy · domain workflows │
             └───────────────────────────────────┘
```

## 3. Repository-to-Architecture Mapping

```text
JARVIS/
├── main.py                 Runtime orchestrator / live session
├── ui.py                   Desktop presentation layer
├── core/                   Infrastructure and governance primitives
│   ├── action_loader.py    Dynamic action discovery + validation
│   ├── plugin_loader.py    Plugin discovery
│   ├── confirm.py          Confirmation gate
│   ├── undo.py             Reversible-action stack
│   ├── wake_word.py        Wake-word lifecycle
│   └── audio_devices.py    Audio device management
├── actions/                Executable capability layer
├── memory/                 Persistent context and session memory
├── plugins/                Optional integrations
├── skills/                 Higher-order operating procedures
├── tools/                  Machine-readable tool contracts
├── dashboard/              Remote control / command center
├── config/                 Local configuration
└── setup.py                Environment bootstrap
```

## 4. Runtime Lifecycle

```text
BOOT
 │
 ├─ load configuration
 ├─ initialize UI/audio
 ├─ discover plugins
 ├─ discover actions
 ├─ load memory
 └─ load system prompt
 │
 ▼
CONNECT
 │
 └─ establish Gemini Live session
 │
 ▼
LISTEN / RECEIVE
 │
 ├─ voice
 ├─ text
 └─ multimodal input
 │
 ▼
INTERPRET
 │
 └─ LLM determines response vs tool call
 │
 ├───────────────┐
 │               │
 ▼               ▼
ANSWER         TOOL CALL
                 │
                 ▼
          GOVERNANCE CHECK
                 │
          ┌──────┴──────┐
          │             │
       allowed       confirmation
          │             │
          └──────┬──────┘
                 ▼
              EXECUTE
                 │
          ┌──────┴──────┐
          ▼             ▼
       result        failure
          │             │
          └──────┬──────┘
                 ▼
             RESPOND
                 │
                 ▼
       MEMORY / SESSION UPDATE
                 │
                 ▼
              CONTINUE
```

## 5. Layer Model

### Layer 0 — Interfaces

Human-facing interfaces: desktop UI, microphone, speaker, camera and remote dashboard.

### Layer 1 — Perception

Captures and normalizes user input. Visual requests must invoke explicit capture tools rather than relying on an assumed visual state.

### Layer 2 — Cognitive Runtime

`main.py` owns the live session, prompt construction, streaming interaction, tool-call lifecycle, reconnect behavior and session state.

### Layer 3 — Capability Fabric

`actions/` contains executable capabilities. `core/action_loader.py` scans action modules, validates their `TOOL` contracts, rejects collisions and constructs an action registry.

### Layer 4 — Memory

Long-term facts and session context are separated so durable information does not become indistinguishable from transient conversation state.

### Layer 5 — Skills

Skills encode repeatable reasoning procedures. A skill should describe **how JARVIS should think/work** for a domain rather than becoming another low-level tool.

### Layer 6 — Governance

Policy, confirmation, reversibility, permissions and audit controls determine whether an intended action may be executed.

## 6. Action Contract

Every discoverable action should expose a module-level `TOOL` dictionary:

```python
TOOL = {
    "name": "example_action",
    "description": "What the action does and when it should be used.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    },
    "handler": example_action,
}
```

The action loader validates:

- tool name syntax;
- non-empty description;
- parameter schema type;
- callable handler;
- reserved-name collisions;
- duplicate action names.

Invalid actions are rejected without aborting the complete discovery scan.

### Action design rules

- One capability per action where practical.
- Explicit parameters; avoid opaque free-form arguments.
- Deterministic side effects.
- Clear error messages.
- No hidden network calls.
- No silent privilege escalation.
- Return machine-usable results where possible.

## 7. Tool Execution Model

```text
LLM intent
   │
   ▼
Tool declaration
   │
   ▼
Argument validation
   │
   ▼
Policy / risk classification
   │
   ├── low risk ───────────────▶ execute
   │
   ├── reversible ─────────────▶ execute + record undo
   │
   ├── consequential ─────────▶ ask confirmation
   │
   └── prohibited ────────────▶ deny
```

JARVIS must never report a side effect as completed solely because the model generated a tool call. Completion requires the tool handler to return a successful execution result.

## 8. Memory Architecture

```text
                 ┌──────────────────┐
                 │ Current Session  │
                 └────────┬─────────┘
                          │ summarize / promote
                          ▼
                 ┌──────────────────┐
                 │ Session Memory   │
                 └────────┬─────────┘
                          │ durable facts
                          ▼
                 ┌──────────────────┐
                 │ Long-Term Memory │
                 └────────┬─────────┘
                          │ retrieve
                          ▼
                 ┌──────────────────┐
                 │ Prompt Context   │
                 └──────────────────┘
```

Memory operations should follow four principles:

1. **Minimality** — store information because it has future utility.
2. **Retrievability** — facts need a stable key/topic representation.
3. **Provenance** — future versions should record where a fact came from.
4. **Governance** — sensitive information must be minimized and protected.

## 9. Skills vs Actions vs Plugins

| Component | Primary purpose | Example |
|---|---|---|
| Action | Execute one governed capability | open app, web search |
| Plugin | Connect external system | Gmail, Calendar |
| Skill | Define a multi-step operating method | CEO Decision Intelligence |
| Core | Runtime infrastructure | discovery, confirmation |
| Memory | Preserve context | user facts, sessions |

A common anti-pattern is putting business logic into `main.py`. New domain behavior should normally be expressed as a skill plus the actions/plugins it requires.

## 10. CEO Decision Intelligence

The CEO Decision layer is a high-level reasoning workflow:

```text
FRAME
 → DIAGNOSE
 → CHANGE
 → PHASE
 → YIN-YANG
 → TIMING
 → OPTIONS
 → SCORE
 → CONSEQUENCES
 → PRE-MORTEM
 → GOVERNANCE
 → RECOMMEND
 → TRIGGERS
 → EXECUTE
 → FEEDBACK
```

This layer must remain decision support, not an unbounded autonomous authority. Recommendations should expose assumptions, uncertainties, trade-offs, risks and decision triggers.

## 11. Proactive Runtime

Background monitoring should be event-oriented rather than continuously active by default:

```text
Topic registered
      ↓
Scheduled check
      ↓
Change detection
      ↓
Relevance / significance filter
      ↓
Alert or suppress
```

Proactive behavior must have an explicit user-controlled scope and must avoid creating unnecessary notification volume.

## 12. Security Architecture

Security controls should be layered:

### Credential security

- Never commit API keys or OAuth secrets.
- Keep credentials in local configuration or secure secret storage.
- Separate development and production credentials.

### Execution security

- Classify tools by risk.
- Require confirmation for high-impact side effects.
- Prefer reversible operations.
- Record undo information when possible.

### Data security

- Minimize stored personal data.
- Avoid copying secrets into prompts.
- Restrict external transmission to the minimum required by a task.

### Supply-chain security

- Pin or constrain critical dependencies where appropriate.
- Review third-party actions/plugins.
- Do not execute arbitrary downloaded code as a normal tool operation.

## 13. Failure Model

JARVIS should degrade gracefully.

```text
Action import failure      → reject action, continue startup
Tool execution failure     → return explicit failure
Network failure            → retry where safe, then explain
LLM disconnect             → reconnect with preserved context
Malformed tool arguments   → reject / request correction
Unauthorized operation     → deny
Unknown result             → report uncertainty
```

The system should favor **explicit failure over fabricated success**.

## 14. Observability

The target architecture should expose structured events for:

- session start/end;
- model connection/reconnection;
- tool selection;
- tool execution start/end;
- confirmation requests;
- policy denials;
- failures;
- memory writes/retrievals;
- proactive alerts.

Future implementations should use correlation IDs so one user request can be traced across reasoning, tools and external systems.

## 15. Evolution to Company OS

The intended evolution is:

```text
JARVIS Desktop Assistant
          │
          ▼
Personal AI Twin
          │
          ▼
AI Employee
          │
          ▼
Multi-Agent Workforce
          │
          ▼
Company OS
```

At Company OS stage, the same primitives become shared organizational infrastructure:

- agent registry;
- role and responsibility model;
- enterprise memory;
- workflow/event bus;
- tool/MCP gateway;
- approval system;
- policy engine;
- identity and access management;
- audit ledger;
- KPI/OKR telemetry;
- executive decision layer.

## 16. Architectural Invariants

These rules should remain true as the system grows:

1. **No fabricated execution.**
2. **No tool without a declared contract.**
3. **No privileged action without an authorization path.**
4. **No irreversible action without appropriate confirmation.**
5. **No memory growth without utility.**
6. **No business-domain expansion that unnecessarily couples `main.py`.**
7. **No autonomy without observability.**
8. **No external side effect without a defined owner and boundary.**

## 17. Target Architecture Roadmap

### Phase 1 — Robust single-agent runtime

- Stable action/plugin discovery.
- Strong confirmation and undo semantics.
- Structured logging.
- Memory provenance.
- Automated tests for core runtime.

### Phase 2 — Agent platform

- Standard agent manifest.
- Tool gateway.
- Event bus.
- Workflow engine.
- Agent-to-agent delegation.
- Policy engine.

### Phase 3 — Company OS

- Organizational identity and RBAC.
- Department/role agents.
- Enterprise knowledge graph.
- Approval chains.
- KPI/OKR execution loop.
- Executive command center.

## 18. Decision Record

This document describes the **current architectural direction**, not a claim that every target component already exists in the repository. Implementations must distinguish clearly between **implemented**, **partially implemented**, and **planned** capabilities.

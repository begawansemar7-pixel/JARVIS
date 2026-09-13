# JARVIS Software Engineering Architecture

> JARVIS SWE Architecture v1.0 — Jcode-inspired, JARVIS-native.

## Purpose

This document defines the Software Engineering (SWE) subsystem of JARVIS. It adopts the strongest engineering ideas observed in `1jehuang/jcode`—context engineering, durable sessions, memory, self-development, model routing and bounded swarm execution—without importing Jcode as a runtime dependency.

JARVIS remains the higher-level AI Employee / Company OS. SWE is a specialist capability under the existing action, governance and memory layers.

## Architectural Principle

> The model proposes and reasons; governed engineering tools inspect, modify, execute, verify and record the result.

## Layered Architecture

```text
Human / JARVIS Executive
          |
          v
     SWE Orchestrator
          |
  +-------+--------+---------+---------+
  |       |        |         |         |
Plan    Code     Test      Review    Debug
  |       |        |         |         |
  +-------+--------+---------+---------+
          |
    Code Intelligence
  +-------+---------+----------------+
  |       |         |                |
Repo Map Symbol Map Dependency Map Context
          |
     Engineering Memory
          |
     Model Router
          |
   Governed Execution
  +-------+--------+---------+
  |       |        |         |
 Git    Shell    Files     External tools
```

## Core Components

### 1. SWE Orchestrator

Coordinates the lifecycle:

`understand -> inspect -> plan -> implement -> test -> repair -> review -> deliver -> learn`.

### 2. Code Intelligence

Builds a lightweight repository map without forcing the model to ingest the whole codebase. It identifies files, symbols, imports, tests, configuration and likely impact areas.

### 3. Engineering Memory

Stores durable engineering facts separately from personal memory: architecture decisions, bugs, fixes, conventions, test failures, active sessions and repository state.

### 4. Model Router

Selects models by task complexity and risk. Planning/reasoning can use a stronger model; extraction, classification and small review tasks can use cheaper/faster models.

### 5. Self-Development

Allows JARVIS to improve its own engineering subsystem only through an explicit, auditable loop. Repository self-modification is denied by default unless an external authorization flag is deliberately enabled.

### 6. Swarm

Uses a task DAG rather than unconstrained agent spawning. Workers are fungible executors of bounded nodes: architect, coder, tester, reviewer and researcher.

## Governance Integration

The SWE subsystem inherits `JARVIS_CONSTITUTION.md` and `ARCHITECTURE.md`.

- Read-only inspection is A0.
- Local reversible edits are A1/A2 depending on scope.
- Repository changes affecting JARVIS itself require explicit self-development authorization.
- Destructive operations require the existing confirmation mechanism.
- Every material engineering session should emit a structured session artifact.

## Compatibility Strategy

JARVIS keeps:

- `actions/dev_agent.py` as the discoverable tool;
- `core/action_loader.py` as the action registry;
- existing Gemini configuration and requirements;
- existing desktop-project workflow;
- existing governance documents.

The implementation is additive and Python-native. Jcode is a design reference, not a dependency.

## Non-Goals

- Replacing JARVIS with a terminal coding agent.
- Copying Jcode source code.
- Introducing Rust solely for architectural imitation.
- Giving autonomous agents unrestricted repository or operating-system authority.

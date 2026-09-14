# JARVIS Skill System

> Status: Engineering design v1.0
> Branch: `feature/jarvis-skill-system`
> Scope: Skill discovery, loading, validation, resolution, execution context, integrity and audit.

## 1. Purpose

The JARVIS Skill System turns domain expertise and repeatable operating procedures into governed, composable, versioned capabilities.

A **Skill is not a tool**. A tool/action performs a bounded capability; a skill defines how JARVIS should reason and work across one or more capabilities.

The system uses `tech-leads-club/agent-skills` as a reference architecture for packaging and progressive disclosure, while preserving JARVIS-native governance, actions, plugins, memory, engineering intelligence and model routing.

## 2. Design Principles

1. **Skill-first domain behavior** — new business behavior should normally be a skill rather than new `main.py` branching.
2. **Governed execution** — skills can request actions, but governance decides whether side effects are permitted.
3. **Progressive disclosure** — metadata is cheap to discover; full instructions and references are loaded only when required.
4. **Explicit dependencies** — skills declare required actions/plugins and execution prerequisites.
5. **Versioned and integrity-checked** — registry and lock metadata make the active skill set reproducible.
6. **Evidence and provenance** — skill outcomes and important decisions can be connected to engineering memory and audit records.
7. **Graceful failure** — one malformed skill must not prevent other skills from loading.
8. **No fabricated execution** — skill completion never implies a side effect succeeded unless the governed action reports success.
9. **Least privilege** — permissions are declared and enforced outside the skill prose.
10. **Composable workflows** — skills may be chained into a controlled Skill DAG.

## 3. Skill Package Contract

Canonical package:

```text
skills/<domain>/<skill>/
├── SKILL.md
├── manifest.yaml
├── references/
├── scripts/
├── assets/
└── tests/
```

`SKILL.md` contains human-readable operating instructions. `manifest.yaml` contains machine-readable identity, dependencies, risk and governance metadata.

Minimum manifest concepts:

```yaml
name: strategy-research
version: 1.0.0
category: strategy
description: Evidence-driven strategic research.
triggers:
  - strategic research
risk_level: low
requires:
  actions: []
  plugins: []
outputs:
  - research brief
governance:
  confirmation: false
```

The runtime treats the manifest as metadata, not as executable code.

## 4. Runtime Architecture

```text
User Intent
    │
    ▼
Skill Discovery
    │  Level 1 metadata
    ▼
Skill Resolution
    │  dependencies + compatibility + risk
    ▼
Skill Loading
    │  Level 2 SKILL.md
    ▼
Context Assembly
    │  Level 3 references/scripts/assets as needed
    ▼
Skill Execution Plan
    │
    ├── Action / Plugin requests
    │          │
    │          ▼
    │    JARVIS Governance
    │          │
    │          ▼
    │       Execute
    │
    ▼
Verification / Outcome
    │
    ▼
Audit + Memory / Session Artifact
```

## 5. Progressive Disclosure

### Level 1 — Discovery metadata

Loaded from the registry: name, version, category, description, triggers, dependencies, risk level and status.

### Level 2 — Skill instructions

Load `SKILL.md` after the skill is selected. This prevents every skill's instructions from consuming the base runtime context.

### Level 3 — Supporting resources

Load only the references, scripts and assets required by the current task.

## 6. Lifecycle

```text
DRAFT → VALIDATING → CERTIFIED → ACTIVE → DEPRECATED → RETIRED
```

A skill becomes `ACTIVE` only after schema, dependency, integrity and relevant quality checks pass.

## 7. Skill Resolution

Resolution should consider:

- explicit user invocation;
- semantic trigger match;
- category/domain;
- skill status;
- version compatibility;
- declared dependencies;
- required actions/plugins;
- risk and permissions;
- conflicts with other selected skills.

The resolver must return a deterministic ranked result rather than silently executing an arbitrary skill.

## 8. Skill and Action Boundary

```text
Skill
  ├── decides workflow
  ├── structures reasoning
  ├── defines required evidence/output
  └── requests capabilities
          │
          ▼
Action / Plugin
  ├── validates parameters
  ├── applies policy
  ├── performs side effect
  └── returns execution result
```

This preserves the existing JARVIS invariant: **the model decides what should happen; governed tools determine what actually happens.**

## 9. Governance Contract

Skill metadata may declare:

- risk level;
- required permissions;
- whether confirmation is required;
- data classification;
- network/filesystem requirements;
- whether external side effects are expected.

These declarations are inputs to policy evaluation. They do not grant permissions.

## 10. Integrity and Supply Chain

The skill registry uses a lock file containing the expected package checksum. Runtime validation should reject integrity mismatches for certified/active skills.

Target chain:

```text
Skill Package
 → Checksum
 → Schema Validation
 → Dependency Validation
 → Permission / Policy Check
 → Execution
 → Audit
```

Downloaded or dynamically supplied executable code must not become a privileged JARVIS action merely because it is packaged as a skill.

## 11. Skill Composition

Complex work should be represented as a DAG rather than a monolithic skill.

Example:

```text
tlc-discover
      ↓
strategy-research
      ↓
market-sizing
      ↓
business-case
      ↓
ceo-decision
      ↓
executive-document
```

Each node has its own contract and verification boundary.

## 12. Evaluation

The JARVIS Quality Gate should evaluate skills against:

- correctness;
- reliability;
- security;
- evidence discipline;
- tool safety;
- test coverage;
- business relevance.

Engineering skills should additionally connect to JARVIS repository intelligence, engineering memory, model routing, verification and repair.

## 13. Relationship to Existing JARVIS

The Skill System must integrate with, not replace:

- `core/action_loader.py` and the existing Action Registry;
- governance/confirmation/undo controls;
- plugins and external integrations;
- memory and session artifacts;
- Software Engineer/Jcode-inspired engineering flow;
- strategy research;
- CEO Decision Intelligence;
- model routing;
- proactive runtime.

No existing SWE or governance implementation should be moved into the Skill Runtime as part of this foundational phase.

## 14. Initial Skill Taxonomy

```text
skills/
├── builtin/
├── product/
├── engineering/
├── strategy/
├── executive/
└── telkom/
```

Telkom-specific skills should remain isolated from generic runtime primitives.

## 15. Engineering Acceptance Criteria

The first implementation is complete when:

- skills can be discovered from a registry;
- invalid manifests are rejected without crashing startup;
- active skills can be loaded from `SKILL.md`;
- dependencies are validated;
- lock/checksum metadata is validated;
- skill resolution is deterministic;
- skill execution receives an explicit context;
- audit events are emitted without performing privileged side effects;
- existing action/governance/SWE modules remain untouched;
- automated tests cover happy path and rejection paths.

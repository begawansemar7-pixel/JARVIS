# JARVIS Skill Architecture

> Status: Architecture baseline v1.0
> Parent architecture: `ARCHITECTURE.md`
> Scope: Skill Platform layer only.

## 1. Architectural Position

JARVIS already defines Skills as higher-order operating procedures. This architecture upgrades that concept into a governed **Skill Platform** without changing the existing Action Registry or Governance Layer.

```text
┌─────────────────────────────────────────────┐
│ Human / CEO / Application                   │
└──────────────────┬──────────────────────────┘
                   ▼
          JARVIS Cognitive Runtime
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Skill Platform                              │
│                                             │
│ Discovery → Registry → Resolver → Loader    │
│              ↓                              │
│        Context / Composition                │
│              ↓                              │
│        Skill Executor                       │
│              ↓                              │
│        Verification                         │
│              ↓                              │
│        Audit / Memory                       │
└───────────────┬─────────────────────────────┘
                │ requests capabilities
                ▼
┌─────────────────────────────────────────────┐
│ Existing JARVIS Capability + Governance    │
│ Action Registry · Plugins · Confirmation   │
│ Undo · Policy · Permissions · Audit        │
└─────────────────────────────────────────────┘
```

## 2. Repository Structure

```text
JARVIS/
├── core/
│   ├── skill_runtime/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── registry.py
│   │   ├── discovery.py
│   │   ├── loader.py
│   │   ├── resolver.py
│   │   ├── validator.py
│   │   ├── executor.py
│   │   ├── context.py
│   │   ├── integrity.py
│   │   └── audit.py
│   └── existing governance/action infrastructure
├── skills/
│   └── <domain>/<skill>/
│       ├── SKILL.md
│       ├── manifest.yaml
│       ├── references/
│       ├── scripts/
│       ├── assets/
│       └── tests/
├── skill-registry/
│   ├── registry.json
│   ├── lock.json
│   └── schemas/
│       ├── manifest.schema.json
│       └── registry.schema.json
├── actions/
├── plugins/
├── memory/
└── tools/
```

## 3. Core Components

### `SkillRegistry`

Authoritative in-process index of valid skills. It does not execute skills.

Responsibilities:

- register validated metadata;
- expose active skills;
- retrieve by ID/name;
- prevent duplicate identity/version conflicts.

### `SkillDiscovery`

Scans configured skill roots and registry metadata. Discovery must be deterministic and resilient to malformed packages.

### `SkillValidator`

Validates manifest schema, required fields, supported lifecycle state and safe path/package boundaries.

### `SkillResolver`

Selects candidate skills based on explicit invocation, triggers, domain, dependencies, compatibility and lifecycle status.

### `SkillLoader`

Loads `SKILL.md` and selected supporting resources after resolution. It must not execute arbitrary scripts during load.

### `SkillContext`

Explicit execution context containing task input, selected skill metadata, session identifiers, available capability references and governance context.

### `SkillExecutor`

Runs the skill operating procedure through an injected execution interface. It must not bypass the Action/Plugin governance boundary.

### `SkillIntegrity`

Computes and verifies package checksums against the lock file.

### `SkillAudit`

Emits structured skill lifecycle events: discovered, rejected, resolved, loaded, execution-start, execution-end, verification and failure.

## 4. Data Flow

```text
Registry metadata
      │
      ▼
Discovery ── invalid ──▶ rejection event
      │
      ▼
Validation
      │
      ▼
Integrity verification
      │
      ▼
Resolver
      │
      ▼
Loader ── SKILL.md ──▶ Context Builder
      │                       │
      └──── references ──────┘
                              ▼
                         Executor
                              │
                       Action requests
                              ▼
                    Existing Governance
                              │
                              ▼
                         Tool result
                              │
                              ▼
                        Verification
                              │
                         Audit/Memory
```

## 5. Manifest Contract

The reference implementation uses YAML package manifests conceptually. The runtime's canonical internal representation is a typed `SkillManifest` model.

Required fields:

- `name`
- `version`
- `category`
- `description`
- `triggers`
- `risk_level`
- `requires`
- `outputs`
- `governance`

Optional fields include author, compatibility, permissions, data classification and tags.

## 6. Registry and Lock

`registry.json` is the human-reviewable active catalog.

`lock.json` is the reproducibility/security record. It records package checksum and version for certified/active skills.

The two files have different purposes and should not be merged:

```text
registry.json → what JARVIS knows
lock.json     → what exact content JARVIS trusts
```

## 7. Resolution Rules

Resolution order:

1. explicit skill name, if supplied;
2. active lifecycle state;
3. trigger/category match;
4. dependency availability;
5. compatibility;
6. risk/permission compatibility;
7. deterministic lexical tie-break.

The resolver returns candidates; execution is a separate operation.

## 8. Security Boundary

```text
             UNTRUSTED / DECLARATIVE
Skill metadata + SKILL.md + references
                    │
                    ▼
              validation/hash
                    │
                    ▼
             trusted context
                    │
                    ▼
          governed capability call
                    │
                    ▼
       Action / Plugin / Governance
                    │
                    ▼
              external effect
```

A skill cannot grant itself a permission. A manifest declaration is advisory until accepted by policy.

## 9. Composition Model

Skill composition should use a DAG with explicit input/output contracts.

```text
Skill A ──output──▶ Skill B ──output──▶ Skill C
   │                  │                  │
   └──── audit ───────┴──── verification┘
```

The initial runtime does not need a workflow engine. The data model should remain compatible with a future workflow engine planned in the parent architecture.

## 10. Compatibility with Existing JARVIS

| Existing subsystem | Skill Platform relationship |
|---|---|
| `core/action_loader.py` | Capability provider; unchanged |
| Governance | Final authority for side effects; unchanged |
| Confirmation | Triggered by governed actions/policy |
| Undo | Owned by existing execution boundary |
| Plugins | External capability provider |
| Memory | Receives useful skill outcomes/lessons |
| SWE/Jcode flow | Exposed as an engineering skill; implementation remains separate |
| Strategy research | Exposed as strategy skill; existing engine remains separate |
| CEO Decision Intelligence | Exposed as executive skill; decision flow remains intact |
| Model router | Can select model for skill execution; remains centralized |

## 11. Non-Goals for v1

- replacing `main.py`;
- replacing `core/action_loader.py`;
- implementing a new policy engine;
- implementing a new workflow engine;
- autonomous arbitrary Python execution;
- moving existing SWE or governance code;
- introducing an external dependency solely for skill loading.

## 12. Future Evolution

```text
v1 Skill Runtime
   ↓
v2 Skill Marketplace / signed registry
   ↓
v3 Skill DAG + Workflow Engine
   ↓
v4 Multi-Agent Skill Federation
   ↓
Company OS Skill Fabric
```

The architecture deliberately keeps v1 small so it can be introduced beside the existing runtime without destabilizing JARVIS.

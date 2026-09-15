# JARVIS 20-Hour Skill Engine

**Status:** Proposed Engineering Specification  
**Version:** 1.0.0  
**Scope:** Skill acquisition runtime, learning/practice orchestration, assessment, scoring, evidence, and state transitions  
**Repository:** `begawansemar7-pixel/JARVIS`

## 1. Purpose

The JARVIS 20-Hour Skill Engine converts a target skill into a bounded, outcome-driven capability sprint inspired by Josh Kaufman's *The First 20 Hours*.

The engine is **not** a course scheduler and does not equate 20 hours with expertise. Its objective is to move a learner from a known starting level to a defined **target performance**, using minimum necessary knowledge, deliberate practice, rapid feedback, evidence-producing work, and assessment.

Core principle:

> **Learning is not the objective. Demonstrated capability is the objective.**

The engine must therefore optimize for:

`TARGET PERFORMANCE -> SKILL DECOMPOSITION -> PRACTICE -> EVIDENCE -> ASSESSMENT -> VERIFIED CAPABILITY`

## 2. Design Goals

1. Represent skills as machine-readable, versioned assets.
2. Decompose a skill into prerequisites, competencies, tasks, and evidence requirements.
3. Generate an adaptive 20-hour plan based on learner baseline and target performance.
4. Separate knowledge acquisition from performance practice.
5. Provide fast feedback after practice activities.
6. Track time without treating elapsed time as proof of competency.
7. Produce auditable evidence artifacts.
8. Score performance using deterministic, explainable rules.
9. Support AI coach interactions without allowing the LLM to bypass state or assessment gates.
10. Expose stable API contracts for JARVIS UI, agents, TANIA, and future integrations.
11. Preserve human authority for high-impact assessments and certification.

## 3. Non-Goals

- Claiming expertise after 20 hours.
- Replacing professional certification where external certification is required.
- Allowing an LLM to self-certify a learner without evidence.
- Treating course completion, chat activity, or time spent as capability proof.
- Building a generic LMS.

## 4. System Context

```text
                         JARVIS CORE
                             |
                    Skill Acquisition Intent
                             |
                             v
                  +-----------------------+
                  | 20-HOUR SKILL ENGINE  |
                  +-----------+-----------+
                              |
        +---------------------+----------------------+
        |                     |                      |
        v                     v                      v
 Skill Registry          Learner Profile       Capability Model
        |                     |                      |
        +---------------------+----------------------+
                              |
                              v
                     Skill Plan Generator
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
            Learn           Practice       Assessment
              |               |               |
              +---------------+---------------+
                              |
                              v
                         Evidence Store
                              |
                              v
                         Score Engine
                              |
                 +------------+------------+
                 |                         |
                 v                         v
             VERIFIED                  REWORK
                 |
                 v
              TANIA
```

## 5. Core Domain Objects

### 5.1 Skill

A reusable definition of a capability that can be learned and assessed.

Required fields:

- `skill_id`
- `version`
- `name`
- `domain`
- `description`
- `target_performance`
- `levels`
- `prerequisites`
- `competencies`
- `practice_tasks`
- `assessment`
- `evidence_requirements`
- `metadata`

### 5.2 Skill Sprint

A learner-specific execution instance of a skill.

Key fields:

- `sprint_id`
- `skill_id`
- `skill_version`
- `learner_id`
- `baseline_level`
- `target_level`
- `target_performance`
- `planned_minutes` (default 1200)
- `consumed_minutes`
- `state`
- `plan`
- `score`
- `evidence_ids`
- timestamps

### 5.3 Learning Activity

A bounded activity intended to provide minimum knowledge needed for performance.

### 5.4 Practice Task

A performance activity requiring the learner to execute a skill, preferably against a realistic case.

### 5.5 Evidence

A verifiable artifact demonstrating performance: code, PRD, analysis, architecture, video, test result, deployed endpoint, business case, etc.

### 5.6 Assessment

A structured evaluation against explicit rubrics. Assessment may be AI-assisted but must use versioned criteria.

## 6. Skill Registry Contract

The canonical registry format is YAML. JSON is the transport representation.

Example:

```yaml
skill_id: AI-RAG-001
version: 1.0.0
status: active
name: Retrieval Augmented Generation
slug: retrieval-augmented-generation
domain: artificial-intelligence
owner: jarvis-capability-team

levels:
  - id: awareness
    threshold: 0
  - id: foundation
    threshold: 40
  - id: practitioner
    threshold: 60
  - id: advanced
    threshold: 75
  - id: expert
    threshold: 90

target_performance:
  statement: Build and evaluate a working RAG prototype for a defined business use case.
  measurable: true
  acceptance_criteria:
    - Explain the RAG architecture and retrieval flow.
    - Ingest a defined knowledge source.
    - Implement retrieval and generation.
    - Evaluate retrieval quality and answer quality.
    - Demonstrate the solution against a test set.

prerequisites:
  - skill_id: LLM-FOUNDATION-001
    minimum_level: foundation

competencies:
  - id: rag-architecture
    name: RAG Architecture
    weight: 15
  - id: ingestion
    name: Data Ingestion
    weight: 15
  - id: retrieval
    name: Retrieval Design
    weight: 20
  - id: generation
    name: Grounded Generation
    weight: 20
  - id: evaluation
    name: RAG Evaluation
    weight: 20
  - id: production-readiness
    name: Production Readiness
    weight: 10

20_hour_plan:
  default_minutes: 1200
  phases:
    - id: orientation
      minutes: 120
      objective: Understand concepts, target performance, and success criteria.
    - id: minimum_knowledge
      minutes: 180
      objective: Acquire only knowledge required to begin execution.
    - id: guided_practice
      minutes: 300
      objective: Complete guided exercises with fast feedback.
    - id: real_case
      minutes: 300
      objective: Build the target outcome on a realistic case.
    - id: independent_build
      minutes: 180
      objective: Reproduce the outcome independently.
    - id: assessment
      minutes: 120
      objective: Produce evidence and complete assessment.

practice_tasks:
  - task_id: RAG-P01
    competency: ingestion
    difficulty: 1
    estimated_minutes: 60
    evidence_required: false
  - task_id: RAG-P02
    competency: retrieval
    difficulty: 2
    estimated_minutes: 90
    evidence_required: false
  - task_id: RAG-P03
    competency: evaluation
    difficulty: 3
    estimated_minutes: 120
    evidence_required: true

assessment:
  method: rubric
  minimum_score: 60
  critical_competencies:
    - retrieval
    - generation
    - evaluation
  human_review_required: true

evidence_requirements:
  minimum_count: 2
  types:
    - architecture
    - executable_artifact
    - evaluation_report

metadata:
  tags: [rag, llm, genai, ai-agent]
  applicable_roles: [ai-product-manager, ai-engineer, solution-architect]
```

## 7. JSON Schema — Skill Registry

The following schema is the minimum implementation contract. Production validation should use JSON Schema Draft 2020-12.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://jarvis.local/schemas/skill.schema.json",
  "title": "JARVIS Skill Registry Entry",
  "type": "object",
  "required": ["skill_id", "version", "status", "name", "domain", "target_performance", "levels", "competencies", "assessment"],
  "properties": {
    "skill_id": { "type": "string", "pattern": "^[A-Z0-9][A-Z0-9._-]+$" },
    "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "status": { "enum": ["draft", "active", "deprecated", "retired"] },
    "name": { "type": "string", "minLength": 1 },
    "slug": { "type": "string" },
    "domain": { "type": "string", "minLength": 1 },
    "owner": { "type": "string" },
    "target_performance": {
      "type": "object",
      "required": ["statement", "measurable", "acceptance_criteria"],
      "properties": {
        "statement": { "type": "string" },
        "measurable": { "type": "boolean" },
        "acceptance_criteria": { "type": "array", "items": { "type": "string" }, "minItems": 1 }
      }
    },
    "levels": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "threshold"],
        "properties": {
          "id": { "type": "string" },
          "threshold": { "type": "number", "minimum": 0, "maximum": 100 }
        }
      },
      "minItems": 1
    },
    "prerequisites": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["skill_id", "minimum_level"],
        "properties": {
          "skill_id": { "type": "string" },
          "minimum_level": { "type": "string" }
        }
      }
    },
    "competencies": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "name", "weight"],
        "properties": {
          "id": { "type": "string" },
          "name": { "type": "string" },
          "weight": { "type": "number", "minimum": 0, "maximum": 100 }
        }
      },
      "minItems": 1
    },
    "20_hour_plan": { "type": "object" },
    "practice_tasks": { "type": "array" },
    "assessment": { "type": "object" },
    "evidence_requirements": { "type": "object" },
    "metadata": { "type": "object" }
  }
}
```

Registry validation must additionally enforce that competency weights sum to 100 and that the 20-hour phase allocation sums to 1200 minutes unless an explicit `planned_minutes` override exists.

## 8. State Machine

The authoritative lifecycle is:

`SKILL -> LEARNING -> PRACTICE -> ASSESSMENT -> VERIFIED`

With controlled recovery paths:

`PRACTICE -> LEARNING` when a prerequisite knowledge gap is detected.  
`ASSESSMENT -> PRACTICE` when evidence is insufficient or score is below threshold.  
`ASSESSMENT -> VERIFIED` only when all verification gates pass.  
`VERIFIED -> REASSESSMENT` only when the skill definition changes materially, evidence expires, or policy requires revalidation.

```text
                         +----------+
                         |  SKILL   |
                         +----+-----+
                              |
                         start_sprint
                              |
                              v
                         +----------+
                         | LEARNING |
                         +----+-----+
                              |
                    learning_gate_passed
                              |
                              v
                         +----------+
                         | PRACTICE |
                         +----+-----+
                              |
                    evidence_ready
                              |
                              v
                       +-------------+
                       | ASSESSMENT  |
                       +------+------+ 
                              |
                 +------------+------------+
                 |                         |
           pass + gates              fail / gaps
                 |                         |
                 v                         v
           +-----------+              +----------+
           | VERIFIED  |              | PRACTICE |
           +-----------+              +----------+
                 ^
                 |
         revalidation required
                 |
           +-------------+
           | REASSESSMENT|
           +-------------+
```

### State semantics

| State | Meaning | Exit condition |
|---|---|---|
| `SKILL` | Skill selected and sprint initialized | Baseline and plan created |
| `LEARNING` | Minimum knowledge acquisition | Learning gate satisfied |
| `PRACTICE` | Deliberate performance work | Required evidence ready |
| `ASSESSMENT` | Evidence evaluated against rubric | Pass or remediation decision |
| `VERIFIED` | Capability verified at target level | Reassessment trigger |
| `REASSESSMENT` | Previously verified skill being revalidated | Pass -> verified; fail -> practice |

Every transition must be persisted as an immutable event.

## 9. Sprint Planning Algorithm

Inputs:

- skill definition
- learner baseline
- target level
- prerequisite state
- available time
- prior evidence
- preferred learning mode

Algorithm:

1. Load immutable skill version.
2. Validate prerequisites.
3. Determine baseline per competency.
4. Remove competencies already demonstrated at or above target threshold, unless required as critical competencies.
5. Allocate the default 1200 minutes across remaining gaps.
6. Insert minimum knowledge activities for identified knowledge gaps.
7. Rank practice tasks by expected learning value and prerequisite order.
8. Reserve assessment and remediation capacity.
9. Generate checkpoints at approximately 25%, 50%, 75%, and 100% progress.
10. Persist the generated plan with a plan version.

The planner must be deterministic for the same inputs and skill version unless an explicit adaptive mode is requested.

## 10. Scoring Engine

### 10.1 Principles

- Time spent is a progress metric, not a competency score.
- Every score maps to an explicit rubric dimension.
- Critical competencies can block verification.
- Scores must be explainable and reproducible.
- LLM-generated assessment is advisory unless a policy explicitly permits automated verification.

### 10.2 Default score model

For each competency `c`:

`competency_score[c] = rubric_score[c] * evidence_quality[c]`

where both are normalized to 0–1.

Overall:

`raw_score = SUM(weight[c] * competency_score[c])`

with weights normalized to 1.

Apply gates:

```text
if raw_score < minimum_score:
    FAIL

if any critical_competency < critical_threshold:
    FAIL

if required_evidence_missing:
    FAIL

if mandatory_human_review && human_review != APPROVED:
    HOLD

else:
    PASS
```

### 10.3 Default rubric

| Dimension | Score 0 | Score 1 | Score 2 | Score 3 | Score 4 |
|---|---|---|---|---|---|
| Knowledge | absent | fragmented | basic | solid | deep |
| Execution | cannot execute | heavily guided | executes basic | independent | robust |
| Quality | unusable | major defects | acceptable | good | production-grade |
| Independence | dependent | frequent help | occasional help | mostly independent | fully independent |
| Business relevance | none | weak | plausible | relevant | directly valuable |

Normalize `0..4` to `0..100`.

### 10.4 Evidence quality

Evidence quality is scored separately:

- `0`: no evidence
- `25`: claimed / unverified
- `50`: partial artifact
- `75`: reproducible artifact
- `100`: reproducible, reviewed, and linked to target performance

The engine should prevent a high self-reported performance score from compensating for missing evidence.

### 10.5 Level mapping

Default mapping:

```text
0-39   awareness
40-59  foundation
60-74  practitioner
75-89  advanced
90-100 expert
```

Skill definitions may override thresholds, but must not create overlapping ranges.

## 11. Evidence Model

Evidence record:

```json
{
  "evidence_id": "EV-01J...",
  "sprint_id": "SPR-01J...",
  "learner_id": "USER-123",
  "type": "executable_artifact",
  "title": "RAG Prototype",
  "uri": "artifact://...",
  "sha256": "...",
  "created_at": "2026-09-15T08:00:00Z",
  "verification": {
    "status": "pending",
    "method": "automated_plus_human"
  }
}
```

Evidence must be immutable once used in a final assessment. A replacement creates a new evidence record.

## 12. API Contract

Base path: `/api/v1/skills`

### POST `/api/v1/skills/sprints`

Create a skill sprint.

Request:

```json
{
  "learner_id": "USER-123",
  "skill_id": "AI-RAG-001",
  "target_level": "practitioner",
  "available_minutes": 1200,
  "adaptive": true
}
```

Response `201`:

```json
{
  "sprint_id": "SPR-01J...",
  "skill_id": "AI-RAG-001",
  "skill_version": "1.0.0",
  "state": "SKILL",
  "target_level": "practitioner",
  "planned_minutes": 1200,
  "consumed_minutes": 0,
  "plan_version": 1
}
```

### GET `/api/v1/skills/sprints/{sprint_id}`

Return current sprint state, progress, next action, score, and evidence summary.

### POST `/api/v1/skills/sprints/{sprint_id}/start`

Transition `SKILL -> LEARNING`.

### POST `/api/v1/skills/sprints/{sprint_id}/activities/{activity_id}/complete`

Record completion and outcome.

Request:

```json
{
  "duration_minutes": 42,
  "outcome": "completed",
  "notes": "Completed ingestion exercise",
  "evidence_ids": []
}
```

### POST `/api/v1/skills/sprints/{sprint_id}/evidence`

Attach evidence to the sprint.

### POST `/api/v1/skills/sprints/{sprint_id}/assessment`

Run or request assessment.

Request:

```json
{
  "mode": "ai_assisted",
  "evidence_ids": ["EV-01J..."],
  "rubric_version": "1.0.0"
}
```

### GET `/api/v1/skills/sprints/{sprint_id}/score`

Return score breakdown, gates, level, and explanation.

### POST `/api/v1/skills/sprints/{sprint_id}/remediate`

Create a remediation plan after failed assessment.

### GET `/api/v1/skills/registry/{skill_id}`

Return active skill definition.

### GET `/api/v1/skills/registry/{skill_id}/versions`

Return available skill versions.

## 13. API Error Contract

```json
{
  "error": {
    "code": "PREREQUISITE_NOT_MET",
    "message": "Required prerequisite LLM-FOUNDATION-001 is below foundation level.",
    "details": {
      "skill_id": "LLM-FOUNDATION-001",
      "required_level": "foundation",
      "current_level": "awareness"
    },
    "request_id": "REQ-01J..."
  }
}
```

Recommended codes:

`SKILL_NOT_FOUND`, `SKILL_VERSION_NOT_FOUND`, `INVALID_STATE_TRANSITION`, `PREREQUISITE_NOT_MET`, `ACTIVITY_NOT_FOUND`, `EVIDENCE_REQUIRED`, `EVIDENCE_INVALID`, `ASSESSMENT_BLOCKED`, `ASSESSMENT_FAILED`, `HUMAN_REVIEW_REQUIRED`, `ALREADY_VERIFIED`.

## 14. Persistence Model

Minimum relational tables:

```text
skills
skill_versions
skill_competencies
skill_prerequisites
skill_tasks
skill_assessments
skill_evidence_requirements
skill_sprints
skill_sprint_activities
skill_evidence
skill_assessments_runs
skill_scores
skill_state_events
```

Recommended indexes:

- `skills(skill_id)` unique
- `skill_versions(skill_id, version)` unique
- `skill_sprints(learner_id, state)`
- `skill_sprints(skill_id, target_level)`
- `skill_evidence(sprint_id)`
- `skill_state_events(sprint_id, created_at)`

## 15. Event Model

Use event-driven state auditing.

Example:

```json
{
  "event_id": "EVT-01J...",
  "aggregate_type": "skill_sprint",
  "aggregate_id": "SPR-01J...",
  "event_type": "SPRINT_STATE_CHANGED",
  "from_state": "LEARNING",
  "to_state": "PRACTICE",
  "actor_type": "system",
  "actor_id": "jarvis",
  "timestamp": "2026-09-15T08:00:00Z",
  "metadata": {}
}
```

Events must not be overwritten. Current state is a projection of the event history plus current sprint data.

## 16. JARVIS Agent Boundary

The LLM may:

- explain concepts;
- recommend the next activity;
- generate exercises;
- provide feedback;
- summarize evidence;
- propose assessment observations.

The LLM may not independently:

- mutate verified state without runtime validation;
- invent evidence;
- mark a missing artifact as present;
- bypass prerequisites;
- override a human-review gate;
- alter historical assessment records.

The runtime remains authoritative for state, persistence, permissions, and scoring gates.

## 17. Security and Governance

1. Learner data must be scoped by tenant/organization.
2. Evidence URIs must enforce authorization.
3. Assessment artifacts must be immutable after finalization.
4. LLM prompts must not be trusted as authorization.
5. Human-review requirements must be policy-driven.
6. Audit events must record actor type and actor ID.
7. Skill definitions require version control and owner approval.
8. A deprecated skill version remains readable for historical assessments.

## 18. Observability

Track:

- sprint starts/completions;
- time-to-first-practice;
- time-to-first-evidence;
- completion rate;
- remediation rate;
- assessment pass rate;
- median score improvement;
- evidence rejection rate;
- average hours to verified capability;
- capability retention/reassessment rate.

Important KPI:

> **Time-to-Verified-Capability**, not time-in-course.

## 19. Acceptance Criteria

The implementation is acceptable when it can:

1. Load and validate a versioned skill definition.
2. Create a learner sprint.
3. Validate prerequisites.
4. Generate a 20-hour plan.
5. Transition through the state machine with invalid transitions rejected.
6. Record activity time and evidence.
7. Run deterministic rubric scoring.
8. Apply critical competency and evidence gates.
9. Produce `VERIFIED` only when all gates pass.
10. Produce remediation when assessment fails.
11. Persist an immutable state-event trail.
12. Expose the documented API contract.
13. Support AI-assisted coaching without giving the LLM authority over state.

## 20. Implementation Order

Recommended repository implementation:

```text
core/skill_runtime/
├── __init__.py
├── models.py
├── states.py
├── transitions.py
├── planner.py
├── scoring.py
├── evidence.py
├── assessment.py
├── events.py
└── service.py

skill-registry/
├── schema/
│   └── skill.schema.json
├── skills/
│   ├── AI-RAG-001.yaml
│   └── ...
└── registry.yaml

skills/20-hour/
└── SKILL.md

tests/skill_runtime/
├── test_registry.py
├── test_state_machine.py
├── test_planner.py
├── test_scoring.py
├── test_evidence.py
└── test_api.py
```

Implementation should start with pure domain logic and tests before integrating persistence or LLM orchestration.

## 21. Definition of Done

The feature is **Done** only when:

- skill definitions are schema-valid;
- all state transitions are tested;
- scoring is deterministic for fixed inputs;
- evidence is auditable;
- API contracts have integration tests;
- AI coaching cannot bypass runtime gates;
- at least one end-to-end skill sprint reaches `VERIFIED` using real evidence;
- at least one failed sprint reaches remediation and can subsequently be reassessed.

## 22. Core Mantra

`DEFINE -> DECONSTRUCT -> LEARN -> PRACTICE -> FEEDBACK -> BUILD -> ASSESS -> VERIFY -> DEPLOY`

The 20-hour engine exists to accelerate the journey from **knowledge to demonstrated capability**.
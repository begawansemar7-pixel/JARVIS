# JARVIS Capability Model

**Status:** Proposed Engineering Specification  
**Version:** 1.0.0  
**Scope:** Capability taxonomy, learner/talent model, skill graph, capability verification, TANIA integration, project matching, and business-impact loop

## 1. Purpose

The JARVIS Capability Model defines the organizational model that connects **business demand, talent, skills, verified performance, assignments, and business impact**.

The model extends the 20-Hour Skill Engine from an individual learning mechanism into an enterprise capability system.

Core principle:

> **Knowledge is an input. Demonstrated performance is a skill. Verified, reusable performance in context is capability. Capability deployed against business demand creates value.**

The target closed loop is:

`BUSINESS DEMAND -> CAPABILITY DEMAND -> TALENT GAP -> SKILL ACQUISITION -> VERIFIED CAPABILITY -> PROJECT MATCH -> BUSINESS IMPACT -> TANIA FEEDBACK`

## 2. Capability Hierarchy

```text
DOMAIN
  |
  +-- CAPABILITY
        |
        +-- COMPETENCY
              |
              +-- SKILL
                    |
                    +-- TASK
                          |
                          +-- EVIDENCE
                                |
                                +-- VERIFIED PERFORMANCE
```

Definitions:

| Object | Definition |
|---|---|
| Domain | Broad professional or technical area |
| Capability | Ability to consistently produce a defined business outcome in context |
| Competency | Component ability required for a capability |
| Skill | Learnable and assessable ability |
| Task | Observable execution unit |
| Evidence | Artifact or observation supporting performance |
| Verified performance | Assessed evidence meeting defined gates |

## 3. Capability vs Skill

A skill is reusable knowledge plus execution ability. A capability adds context, reliability, independence, and business relevance.

Example:

```text
Skill:
"Build a RAG application"

Capability:
"Design, build, evaluate, secure, and operate a RAG solution
for an enterprise use case within defined architecture,
security, cost, and SLA constraints."
```

Therefore the capability model must capture:

- skill proficiency;
- contextual applicability;
- independence;
- evidence quality;
- recency;
- business relevance;
- verified project experience.

## 4. Capability Level Model

Default levels:

```text
L0  Awareness
L1  Foundation
L2  Practitioner
L3  Advanced
L4  Expert
```

### L0 — Awareness

Can explain terminology and recognize common use cases.

### L1 — Foundation

Can perform basic tasks with guidance.

### L2 — Practitioner

Can independently perform defined tasks in normal conditions.

### L3 — Advanced

Can solve non-trivial problems, adapt patterns, review others, and operate with limited supervision.

### L4 — Expert

Can define standards, handle complex ambiguity, mentor others, and make architecture/strategy decisions within the domain.

Expert status should normally require repeated evidence across multiple contexts, not a single 20-hour sprint.

## 5. Capability Dimensions

Capability level is multidimensional.

```text
                 CAPABILITY
                     |
      +--------------+--------------+
      |              |              |
   Knowledge      Execution      Judgment
      |              |              |
      +--------------+--------------+
                     |
              Independence
                     |
              Business Impact
```

Default dimensions:

| Dimension | Weight | Question |
|---|---:|---|
| Knowledge | 15% | Does the person understand the concepts? |
| Execution | 30% | Can the person perform the work? |
| Quality | 20% | Is the output reliable and fit for purpose? |
| Independence | 20% | Can the person work without excessive guidance? |
| Business relevance | 15% | Can the skill be applied to a real business need? |

Skill-specific definitions may override weights, but every override must be versioned.

## 6. Capability State

A talent capability record has two dimensions:

1. **Proficiency state** — current assessed level.
2. **Verification state** — whether sufficient evidence exists.

Verification states:

`UNASSESSED -> CLAIMED -> EVIDENCE_PENDING -> VERIFIED -> EXPIRED`

A learner may have a high self-reported level but remain unverified.

```text
                 +-----------+
                 | UNASSESSED|
                 +-----+-----+
                       |
                    claim
                       v
                 +-----------+
                 |  CLAIMED  |
                 +-----+-----+
                       |
                 evidence
                       v
              +------------------+
              | EVIDENCE_PENDING |
              +--------+---------+
                       |
                    assess
                       v
                 +-----------+
                 | VERIFIED  |
                 +-----+-----+
                       |
                 expiry trigger
                       v
                 +-----------+
                 |  EXPIRED  |
                 +-----------+
```

`EXPIRED` does not erase historical evidence. It means the capability must be revalidated before being treated as current.

## 7. Skill Graph

The Skill Graph represents dependencies and transferability.

Example:

```text
LLM Foundation
      |
      +------> Prompt Engineering
      |              |
      |              +------> RAG
      |                         |
      |                         +------> AI Agent
      |
      +------> Tool Calling
                     |
                     +------> AI Agent
```

Each edge has a relationship type:

- `prerequisite`
- `supports`
- `complements`
- `specializes`
- `supersedes`

Graph traversal is used for:

- gap analysis;
- learning path generation;
- prerequisite validation;
- talent matching;
- capability forecasting.

## 8. Talent Capability Profile

Canonical JSON representation:

```json
{
  "talent_id": "TAL-123",
  "profile_version": 7,
  "capabilities": [
    {
      "skill_id": "AI-RAG-001",
      "skill_version": "1.0.0",
      "level": "practitioner",
      "score": 72,
      "verification_state": "VERIFIED",
      "verified_at": "2026-09-15T08:00:00Z",
      "last_used_at": "2026-09-10T08:00:00Z",
      "evidence_count": 3,
      "contexts": ["enterprise-ai", "product-development"],
      "confidence": 0.91
    }
  ]
}
```

## 9. Capability Evidence

Evidence must capture:

- who produced it;
- when it was produced;
- what skill it demonstrates;
- what context it belongs to;
- whether it is reproducible;
- who/what verified it;
- score and rubric version.

Evidence types:

`artifact`, `project`, `assessment`, `observation`, `simulation`, `production_metric`, `peer_review`, `manager_review`.

Production evidence should carry stronger weight than self-reported claims.

## 10. Capability Confidence

Confidence is separate from proficiency.

A score of 80 with one weak artifact may have lower confidence than a score of 75 supported by three independently reviewed projects.

Default confidence factors:

```text
confidence =
  evidence_strength * 0.40
+ verification_quality * 0.25
+ recency * 0.15
+ repetition * 0.10
+ context_diversity * 0.10
```

All factors normalize to `0..1`.

Confidence should not increase solely because a learner spends more time in the system.

## 11. Recency / Skill Decay

Some skills decay faster than others. The registry may define `validity_days`.

Example:

```yaml
skill_id: AI-SECURITY-001
validity:
  enabled: true
  validity_days: 365
  reassessment_level: advanced
```

For stable skills, validity may be disabled.

Recency is used as a confidence signal and may trigger reassessment. It should not silently downgrade a historical assessment.

## 12. Capability Gap Model

A capability gap compares business demand with current verified supply.

```text
Demand Requirement
       |
       v
Required Capability
       |
       +-------------------+
       |                   |
       v                   v
Current Talent       Available Supply
       |
       +---------+---------+
                 |
                 v
            GAP ANALYSIS
                 |
       +---------+---------+
       |         |         |
       v         v         v
     Build      Buy      Borrow
```

Gap categories:

- `NONE`
- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

## 13. Capability Gap Scoring

For each required skill:

`gap = required_level_score - available_level_score`

Default level scores:

```text
awareness   = 20
foundation  = 40
practitioner= 60
advanced    = 80
expert      = 95
```

Demand priority is calculated as:

`priority = business_criticality * urgency * scarcity * strategic_relevance`

Each factor is normalized to `1..5`.

This produces a ranked capability gap backlog.

## 14. Build / Buy / Borrow Decision

For a gap, JARVIS should recommend one or more mechanisms:

### BUILD

Use 20-Hour Skill Engine, mentoring, project assignments, or structured capability development.

### BUY

Hire or acquire external capability when internal development is too slow, scarce, or strategically inappropriate.

### BORROW

Use partners, contractors, communities, or cross-unit talent sharing.

Decision factors:

- time-to-capability;
- scarcity;
- cost;
- strategic importance;
- retention risk;
- knowledge transfer requirement;
- security/regulatory constraints.

## 15. Project Matching

A project declares capability requirements:

```json
{
  "project_id": "PRJ-AI-001",
  "requirements": [
    {
      "skill_id": "AI-RAG-001",
      "minimum_level": "practitioner",
      "weight": 0.30,
      "critical": true
    },
    {
      "skill_id": "PRODUCT-PRD-001",
      "minimum_level": "advanced",
      "weight": 0.25,
      "critical": false
    }
  ]
}
```

Talent fit:

`fit = SUM(skill_match * requirement_weight) * context_factor * availability_factor`

Hard constraints must be applied before ranking:

- mandatory skill level;
- mandatory certification;
- security clearance where applicable;
- availability;
- conflict-of-interest restrictions.

## 16. Talent Matching Score

Default:

```text
match_score =
  0.50 * capability_fit
+ 0.15 * evidence_strength
+ 0.10 * recency
+ 0.10 * context_relevance
+ 0.10 * availability
+ 0.05 * collaboration_fit
```

A candidate below a mandatory requirement must not be ranked above a candidate that satisfies it merely because of a higher soft score.

## 17. Business Impact Loop

Capability is not complete from an organizational perspective until it is connected to outcomes.

```text
Verified Capability
        |
        v
Project Assignment
        |
        v
Delivery
        |
        v
Business KPI
        |
        v
Value Realization
        |
        v
Capability Reassessment
        |
        +--------> TANIA
```

Examples of business impact:

- revenue generated;
- cost avoided;
- cycle time reduced;
- productivity increased;
- quality improved;
- customer experience improved;
- risk reduced;
- product launched;
- automation achieved.

## 18. Data Model

Minimum relational model:

```text
people
  |
  +--- talent_profiles
          |
          +--- talent_capabilities
          |       |
          |       +--- capability_evidence
          |
          +--- skill_sprints

skills
  |
  +--- skill_versions
          |
          +--- skill_competencies
          +--- skill_prerequisites
          +--- skill_tasks
          +--- skill_assessments

capabilities
  |
  +--- capability_skills
  +--- capability_requirements

projects
  |
  +--- project_skill_requirements
  +--- project_assignments
          |
          +--- business_impacts
```

### Recommended table definitions

```sql
CREATE TABLE skills (
  id UUID PRIMARY KEY,
  skill_id TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  domain TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','active','deprecated','retired')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE skill_versions (
  id UUID PRIMARY KEY,
  skill_id UUID NOT NULL REFERENCES skills(id),
  version TEXT NOT NULL,
  definition JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(skill_id, version)
);

CREATE TABLE talent_capabilities (
  id UUID PRIMARY KEY,
  talent_id UUID NOT NULL,
  skill_id UUID NOT NULL REFERENCES skills(id),
  skill_version_id UUID NOT NULL REFERENCES skill_versions(id),
  level TEXT NOT NULL,
  score NUMERIC(5,2) NOT NULL CHECK (score >= 0 AND score <= 100),
  verification_state TEXT NOT NULL,
  confidence NUMERIC(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  verified_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(talent_id, skill_id, skill_version_id)
);

CREATE TABLE capability_evidence (
  id UUID PRIMARY KEY,
  talent_capability_id UUID NOT NULL REFERENCES talent_capabilities(id),
  evidence_type TEXT NOT NULL,
  title TEXT NOT NULL,
  uri TEXT,
  content_hash TEXT,
  verification_state TEXT NOT NULL,
  reviewer_id UUID,
  rubric_version TEXT,
  score NUMERIC(5,2),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 19. Skill Registry JSON Contract

The capability model consumes the Skill Registry defined by the 20-Hour Engine. Additional capability metadata can be added without changing the core skill contract.

```json
{
  "skill_id": "AI-RAG-001",
  "version": "1.0.0",
  "target_capabilities": [
    {
      "capability_id": "CAP-AI-SOLUTION-001",
      "minimum_level": "practitioner",
      "contexts": ["enterprise-ai", "product-development"]
    }
  ],
  "validity": {
    "enabled": false,
    "validity_days": null
  },
  "evidence_policy": {
    "minimum_count": 2,
    "production_evidence_preferred": true,
    "human_review_required": true
  }
}
```

## 20. API Contract

Base path: `/api/v1/capabilities`

### GET `/api/v1/capabilities/talents/{talent_id}`

Return the current capability profile.

### GET `/api/v1/capabilities/talents/{talent_id}/gaps`

Return ranked capability gaps against the configured role, project, or organizational target.

Query parameters:

`context=role|project|organization`  
`context_id=<id>`

### POST `/api/v1/capabilities/talents/{talent_id}/claims`

Create a self-reported capability claim. This never creates `VERIFIED` status.

Request:

```json
{
  "skill_id": "AI-RAG-001",
  "claimed_level": "practitioner",
  "contexts": ["enterprise-ai"]
}
```

### POST `/api/v1/capabilities/talents/{talent_id}/evidence`

Attach evidence to a capability claim or sprint.

### POST `/api/v1/capabilities/talents/{talent_id}/assessments`

Request an assessment using a specific skill/rubric version.

### GET `/api/v1/capabilities/talents/{talent_id}/passport`

Return a human-readable and machine-readable Skill Passport.

### GET `/api/v1/capabilities/gaps`

Return organization-wide gaps.

Parameters:

`domain`, `criticality`, `role`, `business_unit`, `status`.

### POST `/api/v1/capabilities/match`

Match talents to project requirements.

Request:

```json
{
  "project_id": "PRJ-AI-001",
  "top_k": 10,
  "include_unverified": false
}
```

### POST `/api/v1/capabilities/projects/{project_id}/assignments`

Create a capability-to-project assignment.

### POST `/api/v1/capabilities/impacts`

Record business impact from an assignment.

Request:

```json
{
  "project_id": "PRJ-AI-001",
  "talent_id": "TAL-123",
  "metric": "cycle_time_reduction",
  "baseline": 10,
  "actual": 6,
  "unit": "days",
  "period": "2026-Q3"
}
```

## 21. API Error Contract

```json
{
  "error": {
    "code": "CAPABILITY_NOT_VERIFIED",
    "message": "Talent does not have verified practitioner capability for AI-RAG-001.",
    "details": {
      "talent_id": "TAL-123",
      "skill_id": "AI-RAG-001",
      "required_level": "practitioner",
      "current_level": "foundation",
      "verification_state": "VERIFIED"
    },
    "request_id": "REQ-01J..."
  }
}
```

Recommended codes:

`TALENT_NOT_FOUND`, `SKILL_NOT_FOUND`, `CAPABILITY_NOT_FOUND`, `CAPABILITY_NOT_VERIFIED`, `REQUIREMENT_NOT_MET`, `EVIDENCE_NOT_FOUND`, `PROJECT_NOT_FOUND`, `NO_MATCH_FOUND`, `INVALID_CAPABILITY_STATE`, `POLICY_BLOCKED`.

## 22. TANIA Integration

TANIA should consume JARVIS Capability APIs rather than directly manipulating JARVIS runtime state.

Recommended data flow:

```text
JARVIS Skill Engine
       |
       | verified capabilities
       v
Capability Service
       |
       +----> TANIA Talent Profile
       |
       +----> TANIA Gap Dashboard
       |
       +----> Demand Forecast
       |
       +----> Project Matching
```

TANIA responsibilities:

- talent inventory;
- organizational capability heatmap;
- capability demand forecast;
- gap prioritization;
- talent mobility;
- project staffing intelligence;
- management dashboards.

JARVIS responsibilities:

- coaching;
- skill planning;
- practice;
- evidence collection;
- assessment orchestration;
- verification workflow.

This separation prevents TANIA from becoming another learning application and prevents JARVIS from becoming an HR system of record.

## 23. Capability Heatmap

Example organization-level representation:

```text
Capability                Demand   Supply   Gap       Priority
----------------------------------------------------------------
AI Agent                    127       43     -84       CRITICAL
RAG                          94       51     -43       HIGH
AI Product Management        73       89     +16       LOW
AI Governance                42        9     -33       CRITICAL
Cloud Architecture           48       61     +13       LOW
```

The heatmap must distinguish:

- verified supply;
- claimed supply;
- available supply;
- deployed supply;
- excess/idle supply.

## 24. Capability Forecasting

Future capability demand can be generated from:

- strategic initiatives;
- product roadmap;
- project pipeline;
- technology adoption;
- regulatory requirements;
- attrition/retirement assumptions;
- current capability trends.

Forecast output:

```json
{
  "horizon": "2027",
  "capability": "AI-Agent",
  "required_fte_equivalent": 120,
  "verified_supply": 43,
  "expected_supply": 68,
  "forecast_gap": 52,
  "recommended_action": "BUILD_AND_BORROW"
}
```

## 25. Governance

Capability verification is an organizational trust mechanism.

Rules:

1. Self-claims are never equivalent to verified capability.
2. Skill definitions are versioned.
3. Assessment rubrics are versioned.
4. Evidence is immutable after final assessment.
5. Human review is required for designated critical capabilities.
6. Historical verification remains auditable.
7. Automated scoring must expose its inputs and rubric version.
8. High-impact staffing decisions should provide explainable matching factors.
9. Personal data must be minimized and access-controlled.
10. Capability data must not be used outside its declared organizational purpose without appropriate authorization.

## 26. Metrics

### Talent metrics

- verified capability count;
- time-to-verified-capability;
- skill gap closure rate;
- capability confidence;
- reassessment rate;
- internal mobility rate.

### Learning metrics

- time-to-first-practice;
- evidence completion rate;
- assessment pass rate;
- remediation rate;
- median score improvement.

### Business metrics

- capability-to-project conversion;
- time-to-staff project;
- productivity gain;
- revenue contribution;
- cost avoidance;
- cycle-time reduction;
- project success rate.

North-star metric:

> **Time from identified capability gap to verified capability deployed in business.**

## 27. Reference Architecture

```text
                         BUSINESS STRATEGY
                                |
                                v
                       CAPABILITY DEMAND
                                |
                                v
                         +-------------+
                         |    TANIA    |
                         +------+------+ 
                                |
                         Talent Gap
                                |
                                v
                         +-------------+
                         |   JARVIS    |
                         +------+------+ 
                                |
                      +---------+---------+
                      |                   |
                      v                   v
               Skill Registry        Skill Graph
                      |                   |
                      +---------+---------+
                                |
                                v
                        20-HOUR ENGINE
                                |
                  Learn -> Practice -> Build
                                |
                                v
                           Assessment
                                |
                                v
                       Evidence + Score
                                |
                                v
                      VERIFIED CAPABILITY
                                |
                                v
                        PROJECT MATCHING
                                |
                                v
                         PRODUCT DELIVERY
                                |
                                v
                        BUSINESS IMPACT
                                |
                                +---------> TANIA
```

## 28. Implementation Boundaries

Recommended modules:

```text
core/
├── skill_runtime/
│   ├── models.py
│   ├── states.py
│   ├── transitions.py
│   ├── planner.py
│   ├── scoring.py
│   ├── evidence.py
│   └── service.py
│
├── capability/
│   ├── models.py
│   ├── profile.py
│   ├── gap.py
│   ├── matching.py
│   ├── confidence.py
│   ├── decay.py
│   └── service.py
│
└── events/
    └── capability_events.py

skill-registry/
├── schema/
├── skills/
└── registry.yaml

api/
├── skills.py
└── capabilities.py

tests/
├── skill_runtime/
└── capability/
```

## 29. End-to-End Acceptance Scenario

Given:

- talent `TAL-123` has RAG foundation capability;
- project `PRJ-AI-001` requires RAG practitioner;
- TANIA identifies the gap.

Expected flow:

```text
1. TANIA identifies gap
2. JARVIS receives target skill
3. Skill Registry resolves AI-RAG-001 v1.0.0
4. Prerequisites are validated
5. JARVIS creates 1200-minute sprint
6. Learner completes minimum knowledge
7. Learner performs guided practice
8. Learner builds real case
9. Evidence is attached
10. Assessment is executed
11. Score = 72
12. Critical competencies pass
13. Human review approves
14. State -> VERIFIED / practitioner
15. TANIA receives capability update
16. Matching engine finds PRJ-AI-001
17. Talent is assigned
18. Business impact is recorded
19. Capability profile is updated with context and evidence
```

## 30. Definition of Done

The capability model is implementation-ready when:

- skills are versioned and discoverable;
- capability profiles can be generated from verified skill evidence;
- gap analysis works at talent and organization level;
- project requirements can be represented machine-readably;
- matching applies hard constraints before soft scoring;
- verification status is separate from self-reported proficiency;
- evidence is auditable;
- TANIA can consume capability data through an API;
- business impact can be linked back to capability and assignment;
- all critical state changes are event-audited.

## 31. Core Doctrine

```text
BUSINESS DEMAND
      -> CAPABILITY GAP
      -> SKILL
      -> 20-HOUR SPRINT
      -> PRACTICE
      -> EVIDENCE
      -> ASSESSMENT
      -> VERIFIED CAPABILITY
      -> PROJECT
      -> BUSINESS IMPACT
      -> FEEDBACK
```

The organizational objective is not to maximize training activity.

> **The objective is to continuously increase the organization's verified capability and convert that capability into measurable business impact.**

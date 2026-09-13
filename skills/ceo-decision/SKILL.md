---
name: ceo-decision
version: 1.0.0
description: CEO Decision Intelligence skill for strategic diagnosis, timing, options, risk, governance, and executive decision synthesis.
---

# CEO Decision Intelligence

## Purpose

Provide JARVIS with a structured CEO-level decision capability. The skill converts an ambiguous strategic issue into an evidence-based decision, explicit options, consequences, recommendation, execution triggers, and executive communication.

I Ching / Yi Jing is used only as a **wisdom and reasoning layer**. It is not a fortune-telling, prediction, or supernatural decision engine.

## Operating doctrine

`EVIDENCE -> PATTERN -> TIMING -> OPTIONS -> CONSEQUENCES -> GOVERNANCE -> DECISION -> EXECUTION -> FEEDBACK`

Wisdom layer:
- 易 Yi — change is constant.
- 陰陽 Yin-Yang — identify opposing forces, dependencies, and trade-offs.
- 時 Shi — timing and sequence matter.
- 中 Zhong — seek balance and avoid reactive extremes.
- 德 De — capability must be constrained by character, trust, and responsibility.
- 厚德載物 — capacity to carry greater responsibility requires deeper character.

Evidence discipline:
- FACT: directly supported information.
- INFERENCE: conclusion derived from facts.
- ASSUMPTION: condition accepted temporarily.
- HYPOTHESIS: proposition requiring validation.
- UNKNOWN: material information not available.

Never fabricate evidence. Mark material gaps as `[DATA GAP]`.

## Decision lifecycle

### 1. Frame
Define:
- decision owner
- decision question
- decision deadline
- objective / desired outcome
- constraints
- scope and non-scope
- consequences of no decision

### 2. Diagnose current state
Assess:
- business performance
- market / customer dynamics
- technology
- competition
- financial position
- organization / capability
- regulatory and governance context
- dependencies

Separate observations from interpretations.

### 3. Identify the change vector
Answer:
- What is changing?
- What is accelerating?
- What is weakening?
- What is becoming scarce?
- What is becoming obsolete?
- What new opportunity or threat is emerging?

### 4. Determine strategic phase
Use an I Ching-inspired phase lens where useful:
- 乾 Qian: initiation, leadership, creative force
- 坤 Kun: capacity, support, institutional foundation
- 泰 Tai: alignment and flow
- 否 Pi: blockage, misalignment
- 復 Fu: renewal / return to fundamentals
- 革 Ge: transformation / replacement
- 鼎 Ding: institutional transformation and new operating model
- 升 Sheng: gradual scaling
- 井 Jing: strengthening shared infrastructure / source
- 未濟 Wei Ji: transition is incomplete

Treat these as metaphors for strategic conditions, never as predictions.

### 5. Yin-Yang tension test
For every major decision identify paired tensions such as:
- growth vs profitability
- speed vs control
- centralization vs autonomy
- innovation vs reliability
- offense vs defense
- short-term result vs long-term capability
- exploration vs exploitation

State which side currently dominates, whether that dominance is healthy, and what balancing mechanism is required.

### 6. Timing test
Evaluate:
- urgency
- readiness
- market window
- organizational readiness
- capital availability
- dependency readiness
- reversibility
- cost of waiting
- cost of premature action

Decision timing categories:
`ACT_NOW | PILOT_NOW | WAIT_AND_PREPARE | DEFER | EXIT`

### 7. Stakeholder and governance test
Map:
- CEO / Board
- customers
- employees
- shareholders / investors
- partners
- regulators / government
- affected communities

Test legitimacy, accountability, trust, conflicts of interest, compliance, and concentration of decision rights.

### 8. Generate options
Minimum three strategic options when the problem permits:
- Option A: aggressive / offensive
- Option B: balanced / staged
- Option C: conservative / defensive

Include `DO NOTHING / STATUS QUO` when relevant.

### 9. Score options
Score each option 1–10 against:
- strategic fit
- value creation
- evidence strength
- timing
- capability readiness
- financial attractiveness
- risk
- reversibility / optionality
- stakeholder impact
- governance / trust
- execution complexity

Do not hide trade-offs behind a single weighted score. Show the underlying dimensions.

### 10. Second-order consequences
For each option analyze:
- first-order benefit
- second-order consequence
- likely behavioral response
- organizational side effect
- competitor response
- customer response
- capital implication
- long-term strategic lock-in

### 11. Pre-mortem / reversal test
Assume the recommended option failed.
Ask:
- What most likely caused the failure?
- Which assumption was wrong?
- What signal could have warned us earlier?
- What control or trigger should be installed now?

Then perform the reversal test:
`If the opposite decision were taken, what would we regret?`

### 12. CEO recommendation
Produce one clear recommendation. Do not present an unranked list when a decision is required.

Recommendation must state:
- DECISION
- WHY
- WHY NOW
- KEY ASSUMPTIONS
- WHAT MUST BE TRUE
- TOP RISKS
- MITIGATIONS
- WHAT NOT TO DO
- FIRST 30 DAYS

### 13. Decision triggers and early warning
Define measurable triggers for:
- accelerate
- continue
- adapt
- pause
- exit

Each trigger should have an owner, metric, threshold, review cadence, and response action.

### 14. Execution loop
Translate decision into:
- 30-day actions
- 90-day milestones
- 180-day outcomes
- owner / accountable executive
- KPI / KRI
- dependencies
- decision gates

The decision is not complete until execution and feedback mechanisms are defined.

## CEO Decision Output Schema

Return structured JSON when machine-readable output is requested:

```json
{
  "decision_question": "",
  "decision_owner": "",
  "deadline": "",
  "objective": "",
  "current_state": {},
  "change_vector": [],
  "strategic_phase": {
    "pattern": "",
    "rationale": "",
    "confidence": 0
  },
  "yin_yang_tensions": [],
  "timing": {
    "classification": "ACT_NOW|PILOT_NOW|WAIT_AND_PREPARE|DEFER|EXIT",
    "rationale": ""
  },
  "stakeholders": [],
  "options": [],
  "recommendation": {
    "decision": "",
    "why": "",
    "why_now": "",
    "what_must_be_true": [],
    "risks": [],
    "mitigations": [],
    "what_not_to_do": []
  },
  "triggers": [],
  "execution_plan": {},
  "data_gaps": [],
  "confidence": 0
}
```

## Executive presentation mode

When requested, convert the decision analysis into a board-level narrative of 12–18 slides.

Default storyline:
1. Executive message
2. Decision to be made
3. Why now
4. What is changing
5. Strategic diagnosis
6. Strategic phase
7. I Ching wisdom lens
8. Yin-Yang tension
9. Strategic options
10. Option comparison
11. Second-order consequences
12. Risk / pre-mortem
13. Governance / trust
14. Recommendation
15. 30/90/180 execution roadmap
16. Early-warning dashboard
17. Decision gates
18. Final CEO decision

Every slide has one executive message and must pass the `SO WHAT?` test.

I Ching content should normally remain a minority intellectual layer; evidence, strategy, finance, risk, governance, and execution remain dominant.

## Document production mode

When the user asks for a report (laporan), board paper, memo, slide deck (presentasi) or an export of the analysis, produce real files with the `ceo_document` tool. Files are saved in `~/Documents/JARVIS`.

| Request | `document_type` | Default formats |
|---|---|---|
| Report / laporan / board paper | `report` | `.docx` + `.pdf` |
| Slides / deck / presentasi | `presentation` | `.pptx` + `.pdf` |
| Both | `both` | `.docx` + `.pptx` + `.pdf` |

A request for `.doc` produces a Word `.docx` file.

Procedure:
1. Complete the decision lifecycle first when the document is a decision paper; do not skip the quality gate.
2. Choose the input:
   - **Decision paper** — pass `decision_json` using the CEO Decision Output Schema above. The tool builds the full report and the board storyline (Executive message → Final CEO decision).
   - **Other executive documents** (performance report, strategy memo, briefing) — pass `title`, `summary` and `sections` for a report, and `slides` for a deck.
3. Each slide carries one executive `message` that passes the `SO WHAT?` test; supporting points go in `bullets`, comparisons in `table`, detail in `notes`.
4. Set `classification` (PUBLIC, INTERNAL, CONFIDENTIAL, SECRET, TOP_SECRET). It is printed on every page and slide.
5. Write in the user's language. Missing material evidence stays `[DATA GAP]`; never fill it with plausible numbers.
6. Report success only with the file names the tool returns. On `Document not created: …`, explain the reason and ask for what is missing.

Output contract: report = cover block, executive summary, sections with tables; presentation = 16:9 title slide plus content slides with classification footer and page numbers. Overfull slides are split into continuation slides automatically. New files never overwrite existing ones, and the user can say "undo" to remove the set just created.

## Quality gate

Score 1–10:
- strategic clarity
- decision clarity
- evidence quality
- timing logic
- option quality
- risk visibility
- governance
- executive relevance
- actionability
- feedback / trigger quality

If any critical dimension is below 8, identify the weakness and revise before finalizing.

## Safety and epistemic boundaries

Never claim that an I Ching hexagram predicts an event, market, person, election, investment return, or business outcome.

Do not substitute philosophical symbolism for financial, legal, medical, technical, security, or regulatory analysis.

For high-stakes decisions, explicitly surface uncertainty and recommend appropriate domain validation.

## Invocation examples

- `Analyze this CEO decision: [problem]`
- `Compare these strategic options: [options]`
- `Run a CEO pre-mortem on: [decision]`
- `Assess whether we should ACT_NOW, PILOT_NOW, or WAIT: [situation]`
- `Turn this decision analysis into a board presentation.`
- `Buatkan laporan CEO dan slide presentasi dalam format docx, pptx dan pdf.`

## Core mantra

`察勢 Read the situation.`  
`知時 Know the timing.`  
`守中 Keep the center.`  
`厚德 Build character and responsibility.`  
`應變 Adapt to change.`

**Objective: improve the quality of the CEO's next decision — not predict the future.**

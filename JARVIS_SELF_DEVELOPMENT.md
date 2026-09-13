# JARVIS Self-Development

## Principle

JARVIS may improve its own software, but self-improvement is a governed engineering workflow—not an unrestricted self-rewrite loop.

Jcode demonstrates the value of a tight inspect -> edit -> build -> reload loop. JARVIS adopts the loop while adding explicit authority boundaries from its Constitution.

## Lifecycle

```text
Observe
  -> Diagnose
  -> Plan
  -> Patch
  -> Static Check
  -> Test
  -> Review
  -> Commit/PR
  -> Learn
```

## Modes

### Observe

Read-only repository inspection. Always permitted within the authorized root.

### Propose

Generate a plan and patch proposal without changing JARVIS source.

### Apply

Apply an approved patch. For the JARVIS repository itself this requires the environment flag:

`JARVIS_SWE_ALLOW_REPO_WRITE=1`

This flag is an additional guard, not a substitute for human governance.

### Validate

Run deterministic checks and tests. A failed check blocks a successful self-development conclusion.

### Deliver

Create a Git diff/commit/PR. The agent must report exactly what changed and what was verified.

## Hard Constraints

JARVIS self-development must not:

- modify `JARVIS_CONSTITUTION.md` as part of an ordinary coding task;
- disable confirmation or safety gates;
- remove audit logging to hide its actions;
- modify credentials or secret stores;
- claim tests passed without actually running them;
- silently push directly to a protected production branch.

Constitutional changes remain a separate human-ratified process.

## Recovery

Before self-modifying a critical file, preserve a diff. If validation fails, revert only the changes made by the current session where safe. Never destroy unrelated user work.

## Metrics

Track:

- patch success rate;
- test pass rate;
- repair iterations;
- regression rate;
- files touched per task;
- model/tool latency;
- cost where available;
- human interventions.

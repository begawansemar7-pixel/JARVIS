# JARVIS SWE Swarm

## Design

JARVIS adopts the strongest part of Jcode's swarm evolution: make the task graph primary and agents secondary. Workers are bounded executors of tasks, not autonomous peers with unrestricted authority.

```text
Requirement
   |
   v
Task DAG
 |  |  \
 A  B   C
 |  |  /
   D
   |
 Review
   |
 Deliver
```

## Worker Roles

- **Architect** — repository analysis and implementation plan.
- **Coder** — bounded code changes.
- **Tester** — tests and failure reproduction.
- **Reviewer** — quality/security/architecture review.
- **Researcher** — external documentation and dependency research.

## Scheduling Rules

1. A node becomes runnable only after dependencies succeed.
2. Each worker gets a narrow objective and explicit file scope where possible.
3. Workers cannot grant themselves new permissions.
4. Parallelism is limited by a configurable worker budget.
5. Shared state is represented as artifacts, not hidden conversational assumptions.
6. Integration happens after verification.

## Default DAG

```text
Analyze
  -> Plan
      -> Implement
          -> Unit Test
              -> Review
                  -> Deliver
```

Independent research and test generation can run in parallel after planning.

## Failure Handling

A failed node may be retried if the failure is deterministic and within retry budget. Repeated failure creates an escalation artifact instead of infinite agent loops.

## Audit

Record worker role, task id, inputs, files affected, model selected, start/end time, result and failure reason. Redact credentials and sensitive payloads.

## Future Evolution

- persistent task DAG;
- worktree isolation;
- artifact exchange;
- worker leasing;
- semantic task routing;
- cost-aware scheduling;
- deep/light swarm modes.

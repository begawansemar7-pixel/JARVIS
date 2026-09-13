# JARVIS Code Intelligence

## Objective

Provide the SWE agent with a compact, queryable representation of a repository so that it can reason over relevant code instead of repeatedly loading entire files.

## Repository Map

The first implementation is intentionally dependency-free and filesystem based.

```text
Repository
 |- files
 |- languages
 |- tests
 |- config
 |- entrypoints
 |- symbols
 |- imports
 `- risk hints
```

## Intelligence Levels

### Level 0 — File inventory

Enumerate source files while excluding generated, binary, VCS and cache directories.

### Level 1 — Structural extraction

Extract Python classes/functions and import statements. The interface is intentionally language-neutral so AST adapters for JavaScript/TypeScript/Go/Rust can be added later.

### Level 2 — Dependency graph

Represent `A imports B` edges and use them for impact analysis.

### Level 3 — Task context

Given a task, rank likely relevant files using path/name matching, symbol matches and dependency proximity.

### Level 4 — Semantic intelligence

Future integration: embeddings and graph memory. This is where the strongest Jcode memory/context concepts can be introduced without coupling JARVIS to Jcode.

## Context Contract

A SWE model should receive:

1. task objective;
2. repository root;
3. relevant files;
4. symbol/dependency evidence;
5. relevant engineering memories;
6. current test state;
7. governance constraints.

It should not receive unrelated personal memory.

## Evidence Object

```json
{
  "path": "actions/dev_agent.py",
  "kind": "source",
  "score": 0.92,
  "reasons": ["task keyword", "import dependency"],
  "symbols": ["dev_agent"],
  "imports": ["engineering.swe_agent"]
}
```

## Safety Rules

- Never traverse outside the requested repository root.
- Never read credential files merely because they exist.
- Never execute code during inspection.
- Do not treat filename similarity as proof of semantic relevance.
- Context ranking is advisory; tests and actual code remain authoritative.

## Future Roadmap

- Tree-sitter adapters.
- Symbol-level retrieval.
- Incremental index cache.
- Embedding-backed semantic retrieval.
- Architecture graph.
- Test-to-code coverage mapping.

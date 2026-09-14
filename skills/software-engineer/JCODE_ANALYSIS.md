# jcode analysis — why and how JARVIS uses it

Source studied: [1jehuang/jcode](https://github.com/1jehuang/jcode) at commit `3715943` (release v0.84.0), MIT licence.

## What jcode is

A terminal coding-agent harness written in Rust, in the same category as Claude Code, Codex CLI and OpenCode. Highlights relevant to JARVIS:

| Capability | Notes |
|---|---|
| Headless runs | `jcode run --json` / `--ndjson` with a streamed event protocol |
| Working directory | Global `-C/--cwd` |
| Providers | Claude, OpenAI, Gemini (OAuth or `GEMINI_API_KEY`), Copilot, Azure, OpenRouter, Ollama, LM Studio, any OpenAI-compatible endpoint |
| Efficiency | Very low RAM per session and fast start-up (project benchmarks) |
| Memory | Semantic memory graph with background extraction and consolidation |
| Swarm | Multiple agents in one repo coordinated by `jcode server` |
| Integration surfaces | NDJSON over `run`, a versioned NDJSON harness API over a Unix socket (`jcode api-bridge`, TypeScript SDK), Agent Client Protocol (`jcode acp`), MCP servers |
| Hooks | `pre_tool` hooks can block tool calls |

## Findings that shaped the integration

1. **No approval gate in `run`.** File edits and shell commands execute automatically. `jcode-command-risk` only asks the *model* to justify risky commands and refuses catastrophic ones (`rm -rf /`, `$HOME`, credential stores). `docs/SAFETY_SYSTEM.md` is a design, used only by ambient mode. → JARVIS adds its own guardrails (allow-listed roots, clean tree, work branch, push guard, discard in read-only modes, timeout/cancel, undo).
2. **No read-only / plan flag.** → JARVIS implements `plan` and `review` modes by prompt plus post-run verification that discards any change.
3. **No timeout or max-turns flag.** → Process-group timeout in JARVIS; `JCODE_RUN_AUTO_POKE_MAX_TURNS` caps follow-up turns.
4. **`--ndjson` events** (`start`, `tool_start`, `tool_done{error}`, `done{text,usage}`, `error{message}`) give a reliable final answer and tool telemetry. → Parsed by `engineering/engine.py`, raw stream kept for audit.
5. **Gemini key support** via `GEMINI_API_KEY`. → JARVIS reuses its configured Gemini key, so no separate login is required.
6. **Gemini 3 tool calls fail in v0.84.0** (verified on 2026-09-14 with a Gemini Developer API key). Gemini 2.5 models are no longer available to new API users, so jcode falls back to `gemini-3-flash-preview`, and the second turn of any tool-using run is rejected with HTTP 400 "Function call is missing a thought_signature" — on both the native Gemini route and Gemini's OpenAI-compatible endpoint. Tracked upstream (e.g. jcode issue #518). → JARVIS explains the error and recommends another provider until jcode fixes it.
7. **Swarm needs a running server** and is not exposed through `run`. → Not used in v1; a later version could drive `jcode api-bridge` for multi-agent jobs and live progress.

## Mapping

| JARVIS layer | Responsibility |
|---|---|
| `skills/software-engineer/SKILL.md` | Engineering-lead procedure: clarify, choose mode, delegate, supervise, verify, report |
| `actions/software_engineer.py` | Voice tool: `status`, `start`, `job`, `cancel`; undo registration |
| `engineering/workspace.py` | Git guardrails |
| `engineering/engine.py` | jcode command, environment, NDJSON parsing, timeout |
| `engineering/jobs.py` | Background jobs, commits, reports, completion announcement |
| `engineering/prompt.py` | Operating rules and per-mode method sent to jcode |

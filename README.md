# JARVIS

> **Just A Rather Very Intelligent System**
>
> A multimodal, tool-using personal AI agent designed to operate your computer, search the web, manage memory, automate workflows, and provide executive decision intelligence.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Gemini](https://img.shields.io/badge/LLM-Gemini%20Live-orange.svg)](https://ai.google.dev/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#platform-support)
[![License](https://img.shields.io/badge/License-See%20LICENSE-lightgrey.svg)](LICENSE)

JARVIS is being developed as an **AI Employee / Company OS foundation**: a persistent assistant that can perceive, reason, remember, use tools, execute actions, and support high-value human decisions.

The repository is intentionally modular. Core runtime logic, dynamically discovered actions, plugins, memory, dashboard capabilities, and specialized skills are separated so JARVIS can evolve from a desktop assistant into an extensible agent platform.

---

## Table of Contents

- [Vision](#vision)
- [What JARVIS Can Do](#what-jarvis-can-do)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Core Design Principles](#core-design-principles)
- [CEO Decision Intelligence](#ceo-decision-intelligence)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running JARVIS](#running-jarvis)
- [Tool and Action System](#tool-and-action-system)
- [Memory](#memory)
- [Voice and Wake Word](#voice-and-wake-word)
- [Vision and Computer Interaction](#vision-and-computer-interaction)
- [Plugins](#plugins)
- [Background Monitoring](#background-monitoring)
- [Dashboard](#dashboard)
- [Platform Support](#platform-support)
- [Security and Safety](#security-and-safety)
- [Development](#development)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Vision

JARVIS is designed around a simple shift:

> **From AI that answers questions → to AI that understands context, uses tools, takes action, learns, and helps make decisions.**

The long-term architecture is intended to support:

1. **Personal AI Twin** — persistent identity, preferences, context, and working style.
2. **AI Employee** — agents that execute repeatable operational work.
3. **Executive Copilot** — decision framing, strategic analysis, recommendations, and board-ready outputs.
4. **Company OS** — a common agent, tool, memory, governance, and workflow layer for an AI-native organization.

---

## What JARVIS Can Do

### 🎙️ Multimodal conversational interface

- Real-time voice interaction through Gemini Live.
- Audio input/output using `sounddevice`.
- Desktop UI built with PyQt6.
- Optional wake-word operation (`Hey Jarvis`).
- Session context and long-term memory integration.

### 👁️ Vision

JARVIS can capture and analyze:

- The computer screen.
- Webcam/camera input.
- Visual application state.
- Images and media used by supported workflows.

JARVIS explicitly routes visual requests through the vision tool instead of pretending to see without a capture.

### 🖥️ Computer control

Depending on the operating system and installed actions, JARVIS can interact with:

- Applications.
- Files and folders.
- Browser sessions.
- Clipboard.
- Window management.
- Keyboard and mouse automation.
- System settings.
- Volume and display controls.
- Other OS-level operations exposed as actions.

### 🌐 Web intelligence

The runtime includes capabilities for:

- Web search.
- Browser automation through Playwright.
- Web-page retrieval and parsing.
- News retrieval.
- YouTube transcript access.
- Web-based research workflows.

### 🧠 Memory

JARVIS includes a file-backed memory layer for:

- Saving durable user facts.
- Recalling stored information.
- Searching memory.
- Maintaining session summaries.
- Restoring useful context across sessions.

### 🔧 Extensible tools

Actions are discovered dynamically from `actions/*.py`. A new action can be added without hard-coding another tool branch into `main.py`.

### 📊 Executive decision intelligence

The `skills/ceo-decision` capability provides a structured strategic decision workflow:

`Frame → Diagnose → Change → Phase → Yin-Yang → Timing → Options → Score → Consequences → Pre-mortem → Governance → Recommend → Triggers → Execute → Feedback`

This turns JARVIS from an execution assistant into a **decision-support system for CEOs and executives**.

### 🔔 Proactive monitoring

JARVIS can maintain background monitoring topics and periodically check for developments, allowing the assistant to move from purely reactive interaction toward proactive assistance.

### 📱 Remote dashboard

The dependency stack includes FastAPI/Uvicorn, cryptography, multipart handling, and QR-code support for remote dashboard/control scenarios.

---

## Architecture

At a high level:

```text
                         ┌───────────────────────────┐
                         │        USER / CEO          │
                         │ Voice · Text · Dashboard  │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │        JARVIS CORE        │
                         │ main.py · session loop    │
                         │ prompt · orchestration    │
                         └───────┬─────────┬─────────┘
                                 │         │
                ┌────────────────┘         └─────────────────┐
                ▼                                            ▼
      ┌──────────────────┐                         ┌──────────────────┐
      │ Memory Layer     │                         │ Action Registry  │
      │ long-term facts  │                         │ dynamic tools    │
      │ session context  │                         │ validation       │
      └────────┬─────────┘                         └────────┬─────────┘
               │                                            │
               │                              ┌─────────────┼──────────────┐
               │                              ▼             ▼              ▼
               │                         Computer       Web/Browser     System
               │                         Control        Research        Actions
               │                              │             │              │
               └──────────────────────────────┴─────────────┴──────────────┘
                                              │
                                              ▼
                                   ┌─────────────────────┐
                                   │   Gemini Live LLM   │
                                   │ Reasoning + Vision  │
                                   │ Tool Calling        │
                                   └─────────────────────┘
                                              │
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
                   Skills / Strategy      Plugins             Dashboard
                   CEO Decision           Integrations        Remote Control
```

### Runtime model

`main.py` owns the live session and orchestration. Specialized capabilities are delegated to modular components:

- `core/` — runtime infrastructure and discovery.
- `actions/` — executable tools.
- `memory/` — persistent context.
- `plugins/` — optional integrations.
- `skills/` — higher-level reasoning and operating procedures.
- `dashboard/` — remote control/UI capabilities.
- `config/` — local configuration and API credentials.

---

## Repository Structure

```text
JARVIS/
├── actions/                 # Executable tools discovered at runtime
├── config/                  # Local configuration and API-key handling
├── core/                    # Runtime, action loader, plugin loader, safety gates
├── dashboard/               # Remote dashboard/control capabilities
├── memory/                  # Long-term memory and session management
├── plugins/                 # Optional external integrations
├── skills/
│   └── ceo-decision/        # CEO Decision Intelligence skill
├── tools/                   # Machine-readable tool definitions
├── main.py                  # Main JARVIS runtime
├── ui.py                    # Desktop UI
├── setup.py                 # Platform-aware installation/setup
├── requirements.txt         # Python dependencies
├── LICENSE
└── README.md
```

---

## Core Design Principles

### 1. Tool-first execution

JARVIS should not claim to have performed an operation when it has not actually executed the corresponding tool.

### 2. Dynamic action discovery

Actions expose a module-level `TOOL` definition and handler. The action loader validates and registers them automatically. Invalid actions are rejected without bringing down the entire application.

### 3. Separation of concerns

The conversational runtime should not become a monolith. New capabilities belong in actions, plugins, memory modules, or skills rather than increasingly large hard-coded branches in `main.py`.

### 4. Persistent context

JARVIS separates transient conversation context from durable memory so useful information can survive individual sessions.

### 5. Human authority

Autonomy must be bounded by explicit permissions, confirmation gates, reversibility, and governance. High-impact actions should not be treated the same as low-risk informational operations.

### 6. Cross-platform execution

Platform-specific dependencies are filtered by `pip` markers, while OS-specific actions use native mechanisms where appropriate.

---

## CEO Decision Intelligence

The CEO Decision skill is one of JARVIS's strategic differentiators.

### Decision pipeline

```text
Problem / Decision
       │
       ▼
    FRAME
       │
       ▼
   DIAGNOSE
       │
       ▼
   CHANGE / PHASE
       │
       ▼
   TIMING + OPTIONS
       │
       ▼
  SCORE OPTIONS
       │
       ▼
 CONSEQUENCES / PRE-MORTEM
       │
       ▼
 GOVERNANCE / RISK
       │
       ▼
 RECOMMENDATION
       │
       ▼
 TRIGGERS + EXECUTION
       │
       ▼
     FEEDBACK
```

### Example commands

```text
Analyze this CEO decision: should we build, buy, or partner?

Assess timing: is this the right time to launch the initiative?

Generate strategic options for this business problem.

Run a pre-mortem on this strategy.

Synthesize CEO recommendation.

Build a 30/90/180-day roadmap.

Build a board presentation.
```

The machine-readable definitions live in `tools/ceo_decision_tools.yaml`, while the operating methodology lives in `skills/ceo-decision/SKILL.md`.

---

## Installation

### Prerequisites

- Python 3.10+ recommended.
- A working microphone for voice interaction.
- Speakers/headphones for audio output.
- A Gemini API key.
- Internet access for web search, browser automation, and Gemini Live.

### 1. Clone

```bash
git clone https://github.com/begawansemar7-pixel/JARVIS.git
cd JARVIS
```

### 2. Create a virtual environment

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Run the platform-aware setup

```bash
python setup.py
```

The setup script installs the Python dependencies appropriate to the detected OS and installs the Chromium and Firefox Playwright browsers.

### 4. Start JARVIS

```bash
python main.py
```

On first run, provide the Gemini API key when prompted by the application.

---

## Configuration

Local configuration is kept under `config/`. API credentials should never be committed to Git.

The runtime expects the Gemini API key through the local configuration flow. Do not place production secrets directly in source files.

Typical configuration areas include:

- Gemini API key.
- Voice settings.
- Wake-word settings.
- Input/output audio devices.
- Background monitoring.
- Other plugin-specific credentials.

If you add a new integration, keep credentials isolated from code and provide an example configuration rather than committing secrets.

---

## Running JARVIS

The normal desktop workflow is:

```text
Start JARVIS
   ↓
Establish Gemini Live session
   ↓
Speak / type request
   ↓
JARVIS interprets intent
   ↓
Selects a tool or answers directly
   ↓
Executes action
   ↓
Returns result
   ↓
Updates session / memory when appropriate
```

For actions requiring a reconnect, JARVIS can rebuild the live session while preserving conversation context where appropriate.

---

## Tool and Action System

The action architecture is intentionally designed for extensibility.

Each discoverable action can expose a structure similar to:

```python
TOOL = {
    "name": "example_action",
    "description": "What the action does and when it should be used.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    },
    "handler": example_action,
}
```

The loader scans `actions/*.py`, validates the `TOOL` contract, detects name collisions, and builds the runtime registry.

This means adding a new capability generally follows:

```text
Create action
   ↓
Define TOOL metadata
   ↓
Implement handler
   ↓
Restart JARVIS
   ↓
Action is discovered automatically
```

### Why this matters

It creates a clean path toward a larger agent ecosystem:

- Bundled actions.
- Third-party plugins.
- MCP-compatible tools in future iterations.
- Domain-specific agent skills.
- Enterprise integrations.

---

## Memory

JARVIS has two complementary memory concepts:

### Long-term memory

Durable facts about the user, projects, preferences, relationships, and other information that is genuinely useful across sessions.

### Session memory

Shorter-lived context used to maintain continuity within and around a live conversation.

The runtime exposes memory operations such as:

- `save_memory`
- `recall_memory`
- session summaries
- memory search
- memory formatting for prompts

Memory should be treated as an operational asset, not as an unrestricted data dump. Sensitive information should be minimized and governed appropriately.

---

## Voice and Wake Word

JARVIS uses Gemini Live for real-time conversational interaction and `sounddevice` for audio I/O.

The local wake word is deliberately **opt-in**. It can be installed/enabled from the application's wake-word settings rather than being mandatory during setup.

The runtime also handles console encoding and Windows subprocess behavior so background/system actions are less likely to destabilize the voice session.

---

## Vision and Computer Interaction

JARVIS does not assume it can see the screen merely because a user asks a visual question.

For requests such as:

```text
What is on my screen?
Look at my camera.
Analyze this window.
What am I looking at?
```

JARVIS routes the request through the visual capture capability and then analyzes the resulting image.

This explicit tool boundary is important for reliability and auditability.

---

## Plugins

Plugins provide optional integrations without forcing every deployment to carry every dependency.

The repository contains a plugin discovery mechanism and optional integrations such as:

- Gmail / Google Calendar.
- Smart-home integrations.
- Other external services exposed through the plugin architecture.

A plugin should ideally be:

1. Independently discoverable.
2. Explicit about its tool contract.
3. Isolated from core runtime logic.
4. Safe to disable.
5. Clear about credentials and external side effects.

---

## Background Monitoring

JARVIS includes a proactive monitoring mechanism for user-defined topics.

Conceptually:

```text
User defines topic
       ↓
Monitoring registry
       ↓
Scheduled/background check
       ↓
Detect meaningful change
       ↓
Generate concise alert
       ↓
User decides whether to act
```

The current runtime deliberately restricts certain monitoring categories, such as crypto/financial/trading topics, in its built-in monitor interface.

---

## Dashboard

The project includes a dashboard layer intended to enable remote interaction and control. The dependency stack includes:

- FastAPI.
- Uvicorn.
- Cryptography.
- Multipart request handling.
- QR-code support.

The dashboard architecture can evolve toward a broader **JARVIS Command Center** for:

- Agent status.
- Task execution.
- Monitoring.
- Memory inspection.
- Approval workflows.
- Performance metrics.
- CEO decision dashboards.

---

## Platform Support

| Platform | Status | Notes |
|---|---|---|
| Windows | Supported | Includes Windows-specific automation dependencies where applicable. |
| macOS | Supported | Uses native macOS mechanisms for selected system actions. |
| Linux | Supported | Some system actions require native utilities. |

### Linux native tools

Depending on which actions you use, you may need tools such as:

```text
pactl          volume/audio
brightnessctl  brightness
systemd-run    reminders/jobs
xdg-utils      opening URLs
```

### macOS

Selected system actions use native `osascript`/LaunchAgent mechanisms.

### Windows

Windows-only Python dependencies are automatically selected through `sys_platform` package markers.

---

## Security and Safety

JARVIS can perform real computer actions. Treat it as an agent with side effects, not as a read-only chatbot.

Recommended deployment principles:

- Keep API keys and OAuth credentials out of Git.
- Run JARVIS with the minimum operating-system privileges required.
- Review tools that can modify files, applications, settings, or external services.
- Use confirmation gates for destructive or irreversible operations.
- Keep undo/reversal mechanisms enabled where available.
- Separate informational tools from side-effecting tools.
- Audit new actions before enabling them in production.
- Do not expose a remote dashboard publicly without appropriate authentication, encryption, and network controls.

The target architecture is **bounded autonomy**:

```text
Informational
    ↓
Low-risk reversible action
    ↓
Confirmed action
    ↓
High-impact / irreversible action
    ↓
Explicit human approval
```

---

## Development

Install dependencies using:

```bash
python setup.py
```

Then run:

```bash
python main.py
```

### Adding an action

1. Create `actions/my_action.py`.
2. Implement the handler.
3. Add the module-level `TOOL` dictionary.
4. Make the tool description precise enough for the model to route correctly.
5. Define a strict parameter schema.
6. Handle exceptions inside the action where useful.
7. Restart JARVIS and verify discovery.

### Good action design

A good action should:

- Do one coherent thing.
- Have an unambiguous name.
- Explain when it should and should not be called.
- Validate inputs.
- Return useful results.
- Avoid hidden side effects.
- Be idempotent where practical.
- Provide a reversible path when possible.

---

## Roadmap

JARVIS is positioned to evolve through several layers.

### Phase 1 — Personal Agent

- Stable voice interaction.
- Memory.
- Vision.
- Computer control.
- Web research.
- Reliable action discovery.

### Phase 2 — AI Employee

- Specialized role-based agents.
- Persistent task execution.
- Workflow orchestration.
- Proactive monitoring.
- Approval and governance workflows.
- Richer plugin/tool ecosystem.

### Phase 3 — Executive Intelligence

- CEO Decision Intelligence.
- Strategic scenario planning.
- Board/ExCo briefing generation.
- KPI and performance monitoring.
- Risk and trigger detection.
- Decision-to-execution tracking.

### Phase 4 — Company OS

```text
Human Leadership
       ↓
CEO / Executive Agent
       ↓
Agent Orchestrator
       ↓
Specialist AI Employees
       ↓
Tools / MCP / APIs / Enterprise Systems
       ↓
Memory + Knowledge + Event Bus
       ↓
Execution + Measurement + Feedback
```

The goal is not to replace human leadership. The goal is to make high-quality human decisions and execution dramatically more scalable.

---

## Contributing

Contributions should preserve the architectural principles of the project.

Before submitting a change:

1. Keep secrets out of the repository.
2. Prefer modular actions over changes to the monolithic runtime.
3. Document new tools and side effects.
4. Test platform-specific behavior where applicable.
5. Avoid breaking existing memory and configuration formats.
6. Update documentation when adding a major capability.

---

## License

See [`LICENSE`](LICENSE) for the applicable license terms.

---

## Project

**JARVIS** is an evolving foundation for an autonomous, multimodal, tool-using AI system.

Repository: https://github.com/begawansemar7-pixel/JARVIS

> **The ambition:** not another chatbot — a governed AI system that can think, remember, use tools, execute work, and help leaders make better decisions.

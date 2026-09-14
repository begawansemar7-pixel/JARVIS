"""jcode engine adapter: build the command, run it headless, parse NDJSON events.

    jcode --no-update --quiet -C <repo> -p <provider> [-m <model>] run --ndjson "<prompt>"

stdin is closed so a login bootstrap can never hang waiting for input, the
process runs in its own session so a timeout kills every child it spawned, and
the Gemini key JARVIS already holds is passed as GEMINI_API_KEY when the user
has not configured jcode separately.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import BASE_DIR, EngineerConfig

API_KEYS_PATH = BASE_DIR / "config" / "api_keys.json"


class EngineUnavailable(Exception):
    """jcode is not installed or not runnable; the message is user-facing."""


@dataclass
class EngineResult:
    ok: bool
    text: str = ""
    error: str = ""
    session_id: str = ""
    tools_used: dict[str, int] = field(default_factory=dict)
    tool_errors: int = 0
    usage: dict = field(default_factory=dict)
    exit_code: int | None = None
    timed_out: bool = False
    duration_seconds: float = 0.0


def find_binary(config: EngineerConfig) -> str:
    candidates = [config.binary, str(Path.home() / ".local" / "bin" / "jcode"),
                  str(Path.home() / ".jcode" / "builds" / "stable" / "jcode")]
    for candidate in candidates:
        resolved = shutil.which(candidate) or (candidate if Path(candidate).is_file()
                                               and os.access(candidate, os.X_OK) else None)
        if resolved:
            return resolved
    raise EngineUnavailable(
        "jcode is not installed. Install it (brew install jcode, "
        "or the script from https://jcode.sh) and try again."
    )


def engine_env(config: EngineerConfig) -> dict[str, str]:
    env = dict(os.environ)
    env["JCODE_RUN_AUTO_POKE_MAX_TURNS"] = str(config.max_turns)
    env.setdefault("JCODE_NO_EMOJI", "1")
    env.setdefault("JCODE_NO_TELEMETRY", "1")  # opt out of jcode usage statistics unless the user opts in
    env["GIT_TERMINAL_PROMPT"] = "0"
    if config.provider in ("gemini", "gemini-api") and not (env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY")):
        try:
            key = json.loads(API_KEYS_PATH.read_text(encoding="utf-8")).get("gemini_api_key", "")
        except (OSError, ValueError):
            key = ""
        if key:
            env["GEMINI_API_KEY"] = key
    return env


def build_command(binary: str, config: EngineerConfig, repo: Path, prompt: str) -> list[str]:
    cmd = [binary, "--no-update", "--quiet", "-C", str(repo), "-p", config.provider]
    if config.model:
        cmd += ["-m", config.model]
    return cmd + ["run", "--ndjson", prompt]


def version(config: EngineerConfig) -> str:
    binary = find_binary(config)
    result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=20,
                            stdin=subprocess.DEVNULL)
    return (result.stdout or result.stderr).strip().splitlines()[0] if (result.stdout or result.stderr) else ""


def parse_event(line: str, result: EngineResult) -> dict | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict):
        return None
    kind = event.get("type") or event.get("event") or ""
    if event.get("session_id"):
        result.session_id = str(event["session_id"])
    if kind == "tool_start":
        name = str(event.get("name") or event.get("tool") or "tool")
        result.tools_used[name] = result.tools_used.get(name, 0) + 1
    elif kind == "tool_done" and event.get("error"):
        result.tool_errors += 1
    elif kind == "done":
        result.ok = True
        result.text = str(event.get("text") or "")
        result.usage = event.get("usage") or {}
    elif kind == "error":
        result.ok = False
        result.error = str(event.get("message") or "engine error")[:3000]
    return event


KNOWN_ERROR_HINTS = (
    ("thought_signature",
     "jcode cannot currently run tools with Gemini 3 models: Gemini rejects its tool-call replay "
     "(missing thought_signature, a known jcode issue: https://github.com/1jehuang/jcode/issues/518). "
     "Set another provider (for example claude, openai or openrouter) in config/software_engineer.json, "
     "or retry after upgrading jcode (brew upgrade jcode)."),
)


def with_hint(error: str) -> str:
    for needle, hint in KNOWN_ERROR_HINTS:
        if needle in error:
            return f"{hint}\n\n{error}"
    return error


def _kill(proc: subprocess.Popen) -> None:
    try:
        if sys.platform != "win32":
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
                return
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError):
        pass


def run_engine(config: EngineerConfig, repo: Path, prompt: str, timeout_seconds: int,
               event_log: Path, cancel: threading.Event | None = None) -> EngineResult:
    binary = find_binary(config)
    result = EngineResult(ok=False)
    started = time.monotonic()
    stderr_lines: list[str] = []
    popen_kwargs = {"start_new_session": True} if sys.platform != "win32" else {}
    proc = subprocess.Popen(
        build_command(binary, config, repo, prompt), cwd=str(repo), env=engine_env(config),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", bufsize=1, **popen_kwargs,
    )

    def _drain_stderr():
        for line in proc.stderr:
            stderr_lines.append(line)
            del stderr_lines[:-50]

    threading.Thread(target=_drain_stderr, daemon=True).start()

    def _watchdog():
        while proc.poll() is None:
            if time.monotonic() - started > timeout_seconds:
                result.timed_out = True
                _kill(proc)
                return
            if cancel is not None and cancel.is_set():
                result.error = "cancelled"
                _kill(proc)
                return
            time.sleep(1)

    threading.Thread(target=_watchdog, daemon=True).start()

    event_log.parent.mkdir(parents=True, exist_ok=True)
    with event_log.open("w", encoding="utf-8") as log:
        for line in proc.stdout:
            log.write(line)
            if line.strip():
                parse_event(line, result)
    result.exit_code = proc.wait()
    result.duration_seconds = round(time.monotonic() - started, 1)

    if result.timed_out:
        result.ok = False
        result.error = f"timed out after {timeout_seconds // 60} minute(s)"
    elif result.exit_code != 0 and not result.error:
        result.ok = False
        tail = "".join(stderr_lines).strip()
        result.error = (tail[-800:] if tail else f"jcode exited with code {result.exit_code}")
    elif result.exit_code == 0 and not result.ok and not result.error:
        result.error = "jcode finished without a final answer"
    if result.error:
        result.error = with_hint(result.error)
    return result


__all__ = ["EngineResult", "EngineUnavailable", "build_command", "find_binary", "parse_event",
           "run_engine", "version"]

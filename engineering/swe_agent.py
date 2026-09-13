"""JARVIS Software Engineering Agent.

A compact, JARVIS-native implementation of the most valuable Jcode ideas:
repository-aware context, durable sessions, model routing and bounded
inspect/plan/build/test/repair loops.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from engineering.code_intelligence import render_context, scan_repository
from engineering.memory import add_event, create_session, save_session
from engineering.model_router import choose

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROJECTS = Path.home() / "Desktop" / "JarvisProjects"
MAX_ITERATIONS = 5


def _api_key() -> str:
    path = BASE_DIR / "config" / "api_keys.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["gemini_api_key"]
    except Exception as exc:
        raise RuntimeError(f"Gemini API key unavailable: {exc}")


def _model(model_name: str):
    from google import genai
    client = genai.Client(api_key=_api_key())

    class Wrapper:
        def generate_content(self, contents):
            return client.models.generate_content(model=model_name, contents=contents)

    return Wrapper()


def _clean(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^```[A-Za-z0-9_+-]*\r?\n?", "", text)
    text = re.sub(r"\r?\n?```\s*$", "", text)
    return text.strip()


def _json_response(text: str) -> dict[str, Any]:
    raw = _clean(text)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _safe_repo(path: str | Path) -> Path:
    root = Path(path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Repository/project path does not exist: {root}")
    return root


def _jarvis_repo() -> Path:
    return BASE_DIR.resolve()


def _repo_write_allowed(root: Path) -> bool:
    try:
        root.relative_to(_jarvis_repo())
        return os.getenv("JARVIS_SWE_ALLOW_REPO_WRITE", "0") == "1"
    except ValueError:
        return True


def _plan(description: str, language: str, context: str) -> dict[str, Any]:
    prompt = f"""You are the JARVIS senior software architect.
Create a minimal implementation plan for this task.

Language: {language}
Objective: {description}

Repository context:
{context[:18000]}

Return ONLY JSON:
{{
  "project_name": "snake_case",
  "entry_point": "main.py",
  "run_command": "python main.py",
  "dependencies": [],
  "files": [
    {{"path":"src/example.py","purpose":"...","imports":[]}}
  ],
  "tests": ["python -m pytest -q"]
}}

Rules: keep the change minimal; preserve existing architecture; do not invent files
that are unnecessary; never include secrets; paths must be relative to the project root.
"""
    return _json_response(_model("gemini-flash-latest").generate_content(prompt).text)


def _write_file(root: Path, description: str, plan: dict[str, Any], item: dict[str, Any], existing: str = "") -> str:
    path = item["path"]
    context = existing[:12000]
    prompt = f"""You are a production {plan.get('language', 'software')} engineer working inside an existing repository.
Task: {description}
File: {path}
Purpose: {item.get('purpose','')}
Related imports: {item.get('imports', [])}
Existing file content (may be empty):
{context}

Return ONLY the complete file content. Preserve existing behavior unless the task requires a change.
No markdown fences. No TODO placeholders. No fake APIs. Do not modify unrelated functionality.
"""
    code = _clean(_model("gemini-flash-latest").generate_content(prompt).text)
    target = (root / path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"Refusing path outside repository: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(code, encoding="utf-8")
    return code


def _run(command: str, root: Path, timeout: int) -> str:
    parts = command.split()
    if not parts:
        return "No command supplied."
    if parts[0] == "python":
        parts[0] = sys.executable
    try:
        result = subprocess.run(parts, cwd=str(root), capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return f"TIMEOUT after {timeout}s"
    except Exception as exc:
        return f"EXECUTION_ERROR: {exc}"
    output = []
    if result.stdout.strip():
        output.append("STDOUT:\n" + result.stdout.strip())
    if result.stderr.strip():
        output.append("STDERR:\n" + result.stderr.strip())
    output.append(f"EXIT_CODE: {result.returncode}")
    return "\n\n".join(output)


def _failed(output: str) -> bool:
    return "EXIT_CODE: 0" not in output or output.startswith("TIMEOUT") or output.startswith("EXECUTION_ERROR")


def _repair(root: Path, description: str, output: str, files: list[dict[str, Any]]) -> list[str]:
    prompt = f"""You are the JARVIS debugging engineer.
Task: {description}
Failure:
{output[:12000]}
Candidate files:
{json.dumps(files, indent=2)[:10000]}
Return ONLY JSON: {{"files":["relative/path.py"],"diagnosis":"short diagnosis","changes":["..." ]}}
"""
    data = _json_response(_model("gemini-flash-latest").generate_content(prompt).text)
    return [str(x) for x in data.get("files", [])][:5]


def run(parameters: dict, player=None, speak: Callable[[str], None] | None = None) -> str:
    p = parameters or {}
    description = str(p.get("description", "")).strip()
    if not description:
        return "Please describe the software task."
    language = str(p.get("language", "python")).strip() or "python"
    mode = str(p.get("mode", "build")).lower().strip()
    timeout = max(5, min(int(p.get("timeout", 60)), 600))
    requested_root = str(p.get("repo_path", "")).strip()
    root = _safe_repo(requested_root) if requested_root else DEFAULT_PROJECTS / re.sub(r"[^A-Za-z0-9_.-]", "_", p.get("project_name", "jarvis_project"))
    root.mkdir(parents=True, exist_ok=True)

    choice = choose(description, configured_model="gemini-flash-latest", configured_provider="gemini")
    session = create_session(root, description, mode, choice.model)
    add_event(session, "task_received", root=str(root), routing=choice.__dict__)

    if root == _jarvis_repo() or _jarvis_repo() in root.parents:
        if not _repo_write_allowed(root) and mode in {"build", "apply", "selfdev"}:
            add_event(session, "write_blocked", reason="JARVIS_SWE_ALLOW_REPO_WRITE is not enabled")
            session["status"] = "blocked"
            save_session(root, session)
            return ("SWE self-modification is blocked by default. "
                    "Run in plan/review mode, or explicitly authorize repository writes with "
                    "JARVIS_SWE_ALLOW_REPO_WRITE=1.")

    if player:
        player.write_log(f"[SWE] {mode.upper()} | {root}")

    inventory = scan_repository(root)
    context = render_context(root, description, limit=10)
    add_event(session, "repository_indexed", files=len(inventory))

    try:
        plan = _plan(description, language, context)
    except Exception as exc:
        session["status"] = "failed"
        add_event(session, "planning_failed", error=str(exc))
        save_session(root, session)
        return f"SWE planning failed: {exc}"

    add_event(session, "plan_created", plan=plan)
    if mode in {"plan", "review"}:
        session["status"] = "planned"
        save_session(root, session)
        files = [x.get("path") for x in plan.get("files", [])]
        return "SWE plan created.\n\n" + json.dumps({"root": str(root), "files": files, "tests": plan.get("tests", []), "mode": mode}, indent=2)

    files = plan.get("files", [])
    touched: list[str] = []
    for item in files:
        path = str(item.get("path", "")).strip()
        if not path:
            continue
        target = (root / path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            continue
        old = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
        try:
            _write_file(root, description, plan, item, old)
            touched.append(path)
            add_event(session, "file_written", path=path)
        except Exception as exc:
            add_event(session, "file_write_failed", path=path, error=str(exc))
            session["status"] = "failed"
            save_session(root, session)
            return f"SWE failed while writing {path}: {exc}"

    session["files_touched"] = touched
    tests = plan.get("tests") or ([plan.get("run_command")] if plan.get("run_command") else [])
    last = ""
    for iteration in range(1, MAX_ITERATIONS + 1):
        command = tests[0] if tests else plan.get("run_command", "")
        last = _run(str(command), root, timeout)
        add_event(session, "verification", iteration=iteration, command=command, output=last[:5000])
        if not _failed(last):
            session["status"] = "passed"
            session["tests"] = [{"command": command, "status": "passed"}]
            save_session(root, session)
            msg = f"SWE task completed after {iteration} verification pass(es).\nRoot: {root}\nFiles: {', '.join(touched)}\n\n{last}"
            if speak:
                speak(msg)
            return msg
        if iteration == MAX_ITERATIONS:
            break
        try:
            repair_files = _repair(root, description, last, files)
            for path in repair_files:
                target = root / path
                old = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
                item = next((x for x in files if x.get("path") == path), {"path": path, "purpose": "repair failing implementation", "imports": []})
                _write_file(root, description, plan, item, old)
                if path not in touched:
                    touched.append(path)
        except Exception as exc:
            add_event(session, "repair_failed", error=str(exc))
            break

    session["status"] = "failed"
    session["files_touched"] = touched
    save_session(root, session)
    return f"SWE could not reach a passing state after {MAX_ITERATIONS} iterations.\nRoot: {root}\nLast verification:\n{last[:6000]}"

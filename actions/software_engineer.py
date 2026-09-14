"""Software engineer engine: JARVIS delegates coding work to jcode in a guarded git branch.

Side-effect class A2 (AGENTS.md §9): modifies files and runs commands inside an
allowed local git repository, on a dedicated branch, with pushing blocked. The
work can be undone through core/undo (back to the base branch, work branch
deleted). The engine sends project code to the configured model provider.

Operations:
    status   — is jcode installed, which provider/folders are configured
    start    — launch a background job (implement | plan | review)
    job      — status or result of a job (latest when no job_id)
    cancel   — stop a running job
"""
from __future__ import annotations

import threading

from core.undo import push_undo
from engineering.config import load_config
from engineering.engine import EngineUnavailable, engine_env, find_binary, version
from engineering.jobs import JobManager
from engineering.workspace import WorkspaceError

_manager: JobManager | None = None
_manager_lock = threading.Lock()


def _get_manager() -> JobManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = JobManager(load_config())
        return _manager


def _status(manager: JobManager) -> str:
    cfg = manager.config
    try:
        find_binary(cfg)
        engine = f"jcode ready ({version(cfg) or 'version unknown'})"
    except EngineUnavailable as e:
        engine = str(e)
    except Exception as e:
        engine = f"jcode found but not runnable ({type(e).__name__})"
    running = [j.id for j in manager.jobs.values() if j.status in ("queued", "running")]
    credentials = ""
    if cfg.provider in ("gemini", "gemini-api"):
        env = engine_env(cfg)
        has_key = bool(env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY"))
        credentials = (" Gemini key: available." if has_key else
                       " Gemini key: missing — fill gemini_api_key in config/api_keys.json, or run "
                       "`jcode login --provider gemini`.")
    return (f"Engine: {engine}.{credentials} Provider: {cfg.provider}{' / ' + cfg.model if cfg.model else ''}. "
            f"Allowed project folders: {', '.join(str(r) for r in cfg.allowed_roots)}. "
            f"Running jobs: {', '.join(running) or 'none'}.")


def _start(manager: JobManager, params: dict, speak, player) -> str:
    find_binary(manager.config)  # fail fast with install guidance
    job = manager.start(
        project_path=str(params.get("project_path") or ""),
        task=str(params.get("task") or ""),
        mode=str(params.get("mode") or "implement").strip().lower(),
        context=str(params.get("context") or ""),
        timeout_minutes=params.get("timeout_minutes"),
        notify=speak,
    )
    ws = job.workspace

    def _undo(job=job):
        if job.status in ("queued", "running"):
            manager.cancel(job.id)
            return "The job was still running; I cancelled it. Say undo again once it has stopped."
        return ws.abandon()

    push_undo(f"engineering job {job.id} on branch {ws.work_branch}", _undo)
    if player:
        try:
            player.write_log(f"SYS: Engineering job {job.id} started on {ws.work_branch}")
        except Exception:
            pass
    return (f"Started engineering job {job.id} ({job.mode}) in {job.repo.name} on branch "
            f"{ws.work_branch}. It runs in the background; I will report when it finishes.")


def software_engineer(parameters: dict, player=None, speak=None) -> str:
    params = parameters or {}
    operation = str(params.get("operation") or "status").strip().lower()
    try:
        manager = _get_manager()
        if operation == "status":
            return _status(manager)
        if operation == "start":
            return _start(manager, params, speak, player)
        if operation == "job":
            job = manager.get(params.get("job_id"))
            if job is None:
                return "No engineering job found."
            summary = manager.summary(job)
            if job.result and job.result.text and job.status not in ("queued", "running"):
                summary += "\nEngine final report (excerpt):\n" + job.result.text.strip()[:3000]
            return summary
        if operation == "cancel":
            job_id = str(params.get("job_id") or "")
            return f"Cancelling job {job_id}." if manager.cancel(job_id) else f"No running job {job_id}."
        return f"Unknown operation '{operation}'. Use status, start, job or cancel."
    except (WorkspaceError, EngineUnavailable, ValueError) as e:
        return f"Engineering job not started: {e}"
    except Exception as e:
        print(f"[SoftwareEngineer] {operation} failed: {type(e).__name__}: {e}")
        return f"Software engineer {operation} failed ({type(e).__name__})."


TOOL = {
    "name": "software_engineer",
    "description": (
        "Software engineer engine powered by jcode, an autonomous coding agent. Use for real work on an "
        "EXISTING local git project: implement a feature, fix a bug, write tests, refactor, upgrade "
        "dependencies (mode=implement); design an implementation plan (mode=plan); or review code for "
        "bugs and security issues (mode=review). Pass project_path (inside the configured project "
        "folders) and a precise task with acceptance criteria. The job runs in the background on a new "
        "jarvis/... branch with git push blocked; say you started it, then report when the "
        "[ENGINEERING_JOB] message arrives or when the user asks (operation=job). The working tree "
        "must be clean. Never claim code was written or tests passed before the job reports it. "
        "Use dev_agent instead to scaffold a brand-new project from scratch, and code_helper for a "
        "single small file."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "operation": {"type": "STRING", "description": "status | start | job | cancel. Default status."},
            "project_path": {"type": "STRING", "description": "start: path of the git repository to work in."},
            "task": {"type": "STRING", "description": "start: what to build or fix, with acceptance criteria."},
            "mode": {"type": "STRING", "description": "start: implement | plan | review. Default implement."},
            "context": {"type": "STRING", "description": "start: optional extra context (constraints, files, tickets)."},
            "timeout_minutes": {"type": "INTEGER", "description": "start: time limit, default 20, max 60."},
            "job_id": {"type": "STRING", "description": "job/cancel: job id such as SE1; job defaults to the latest."},
        },
        "required": ["operation"],
    },
    "handler": software_engineer,
}

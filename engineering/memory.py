"""Durable, dependency-free engineering memory for SWE sessions."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


def memory_root(repo: str | Path) -> Path:
    return Path(repo).expanduser().resolve() / "memory" / "engineering" / "sessions"


def create_session(repo: str | Path, objective: str, mode: str, model: str) -> dict[str, Any]:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "id": f"swe-{uuid.uuid4().hex[:12]}",
        "objective": objective,
        "mode": mode,
        "model": model,
        "created_at": now,
        "updated_at": now,
        "status": "running",
        "files_touched": [],
        "tests": [],
        "events": [],
    }


def add_event(session: dict[str, Any], event: str, **data: Any) -> None:
    session["events"].append({"at": time.time(), "event": event, **data})
    session["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def save_session(repo: str | Path, session: dict[str, Any]) -> Path:
    target = memory_root(repo)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{session['id']}.json"
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_sessions(repo: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    root = memory_root(repo)
    if not root.exists():
        return []
    paths = sorted(root.glob("swe-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    result: list[dict[str, Any]] = []
    for path in paths[:limit]:
        try:
            result.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return result

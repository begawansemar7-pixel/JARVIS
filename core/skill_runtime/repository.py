from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol

from .models import AssessmentResult, Evidence, SkillSprint


class SkillRepository(Protocol):
    def save_sprint(self, sprint: SkillSprint) -> None: ...
    def get_sprint(self, sprint_id: str) -> SkillSprint | None: ...
    def list_sprints(self, learner_id: str | None = None) -> list[SkillSprint]: ...
    def save_idempotency(self, key: str, operation: str, sprint_id: str) -> None: ...
    def get_idempotency(self, key: str, operation: str) -> str | None: ...
    def append_event(self, event: dict[str, Any]) -> None: ...
    def list_events(self, sprint_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]: ...


def _evidence_to_dict(e: Evidence) -> dict[str, Any]:
    return {"evidence_id": e.evidence_id, "kind": e.kind, "title": e.title, "score": e.score, "metadata": e.metadata}


def _assessment_to_dict(a: AssessmentResult | None) -> dict[str, Any] | None:
    if a is None:
        return None
    return {"knowledge": a.knowledge, "execution": a.execution, "quality": a.quality,
            "independence": a.independence, "business_relevance": a.business_relevance,
            "evidence_score": a.evidence_score, "passed": a.passed, "feedback": a.feedback}


def sprint_to_dict(s: SkillSprint) -> dict[str, Any]:
    return {"sprint_id": s.sprint_id, "skill_id": s.skill_id, "learner_id": s.learner_id,
            "state": s.state, "hours_completed": s.hours_completed,
            "evidence": [_evidence_to_dict(e) for e in s.evidence],
            "assessment": _assessment_to_dict(s.assessment), "version": s.version}


class SQLiteSkillRepository:
    def __init__(self, path: str | Path = "data/jarvis_skills.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS skill_sprints (
                sprint_id TEXT PRIMARY KEY, skill_id TEXT NOT NULL, learner_id TEXT NOT NULL,
                state TEXT NOT NULL, hours_completed REAL NOT NULL DEFAULT 0,
                evidence_json TEXT NOT NULL DEFAULT '[]', assessment_json TEXT,
                version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_sprints_learner ON skill_sprints(learner_id)")
            conn.execute("""CREATE TABLE IF NOT EXISTS skill_idempotency (
                idempotency_key TEXT NOT NULL, operation TEXT NOT NULL, sprint_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (idempotency_key, operation)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS skill_events (
                event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, sprint_id TEXT, skill_id TEXT,
                learner_id TEXT, idempotency_key TEXT, payload_json TEXT NOT NULL DEFAULT '{}',
                occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_events_sprint ON skill_events(sprint_id, occurred_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_events_learner ON skill_events(learner_id, occurred_at)")

    def save_sprint(self, sprint: SkillSprint) -> None:
        payload = sprint_to_dict(sprint)
        with self._connect() as conn:
            conn.execute("""INSERT INTO skill_sprints
                (sprint_id, skill_id, learner_id, state, hours_completed, evidence_json, assessment_json, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sprint_id) DO UPDATE SET state=excluded.state,
                hours_completed=excluded.hours_completed, evidence_json=excluded.evidence_json,
                assessment_json=excluded.assessment_json, version=excluded.version, updated_at=CURRENT_TIMESTAMP""",
                (sprint.sprint_id, sprint.skill_id, sprint.learner_id, sprint.state, sprint.hours_completed,
                 json.dumps(payload["evidence"]), json.dumps(payload["assessment"]) if payload["assessment"] else None,
                 sprint.version))

    def get_sprint(self, sprint_id: str) -> SkillSprint | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM skill_sprints WHERE sprint_id=?", (sprint_id,)).fetchone()
        return self._row_to_sprint(row) if row else None

    def list_sprints(self, learner_id: str | None = None) -> list[SkillSprint]:
        with self._connect() as conn:
            rows = (conn.execute("SELECT * FROM skill_sprints WHERE learner_id=? ORDER BY updated_at DESC", (learner_id,)).fetchall()
                    if learner_id else conn.execute("SELECT * FROM skill_sprints ORDER BY updated_at DESC").fetchall())
        return [self._row_to_sprint(r) for r in rows]

    def save_idempotency(self, key: str, operation: str, sprint_id: str) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO skill_idempotency(idempotency_key, operation, sprint_id) VALUES (?, ?, ?)",
                         (key, operation, sprint_id))

    def get_idempotency(self, key: str, operation: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT sprint_id FROM skill_idempotency WHERE idempotency_key=? AND operation=?", (key, operation)).fetchone()
        return row["sprint_id"] if row else None

    def append_event(self, event: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute("""INSERT INTO skill_events
                (event_id, event_type, sprint_id, skill_id, learner_id, idempotency_key, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (event["event_id"], event["event_type"], event.get("sprint_id"), event.get("skill_id"),
                 event.get("learner_id"), event.get("idempotency_key"), json.dumps(event.get("payload", {}), default=str)))

    def list_events(self, sprint_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._connect() as conn:
            rows = (conn.execute("SELECT * FROM skill_events WHERE sprint_id=? ORDER BY occurred_at DESC LIMIT ?", (sprint_id, limit)).fetchall()
                    if sprint_id else conn.execute("SELECT * FROM skill_events ORDER BY occurred_at DESC LIMIT ?", (limit,)).fetchall())
        return [{"event_id": r["event_id"], "event_type": r["event_type"], "sprint_id": r["sprint_id"],
                 "skill_id": r["skill_id"], "learner_id": r["learner_id"], "idempotency_key": r["idempotency_key"],
                 "payload": json.loads(r["payload_json"] or "{}"), "occurred_at": r["occurred_at"]} for r in rows]

    @staticmethod
    def _row_to_sprint(row: sqlite3.Row) -> SkillSprint:
        s = SkillSprint(row["sprint_id"], row["skill_id"], row["learner_id"])
        s.state, s.hours_completed, s.version = row["state"], row["hours_completed"], row["version"]
        for e in json.loads(row["evidence_json"] or "[]"):
            s.evidence.append(Evidence(e["evidence_id"], e["kind"], e["title"], e["score"], e.get("metadata", {})))
        if row["assessment_json"]:
            s.assessment = AssessmentResult(**json.loads(row["assessment_json"]))
        return s


class SupabaseSkillRepository:
    """Supabase REST adapter using the JARVIS skill runtime tables."""
    def __init__(self, url: str, key: str, table: str = "jarvis_skill_sprints"):
        import requests
        self.url, self.key, self.table = url.rstrip("/"), key, table
        self._requests = requests

    @property
    def _endpoint(self):
        return f"{self.url}/rest/v1/{self.table}"

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}"}
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _table_endpoint(self, table: str) -> str:
        return f"{self.url}/rest/v1/{table}"

    def save_sprint(self, sprint: SkillSprint) -> None:
        self._requests.post(self._endpoint, headers=self._headers("resolution=merge-duplicates,return=representation"),
                            json=sprint_to_dict(sprint), timeout=15).raise_for_status()

    def get_sprint(self, sprint_id: str) -> SkillSprint | None:
        r = self._requests.get(self._endpoint, params={"sprint_id": f"eq.{sprint_id}", "limit": 1}, headers=self._headers(), timeout=15)
        r.raise_for_status()
        rows = r.json()
        return self._dict_to_sprint(rows[0]) if rows else None

    def list_sprints(self, learner_id: str | None = None) -> list[SkillSprint]:
        params = {"order": "updated_at.desc"}
        if learner_id:
            params["learner_id"] = f"eq.{learner_id}"
        r = self._requests.get(self._endpoint, params=params, headers=self._headers(), timeout=15)
        r.raise_for_status()
        return [self._dict_to_sprint(x) for x in r.json()]

    def save_idempotency(self, key: str, operation: str, sprint_id: str) -> None:
        self._requests.post(self._table_endpoint("jarvis_skill_idempotency"), headers=self._headers("resolution=ignore-duplicates"),
                            json={"idempotency_key": key, "operation": operation, "sprint_id": sprint_id}, timeout=15).raise_for_status()

    def get_idempotency(self, key: str, operation: str) -> str | None:
        r = self._requests.get(self._table_endpoint("jarvis_skill_idempotency"),
                               params={"idempotency_key": f"eq.{key}", "operation": f"eq.{operation}", "limit": 1},
                               headers=self._headers(), timeout=15)
        r.raise_for_status()
        rows = r.json()
        return rows[0]["sprint_id"] if rows else None

    def append_event(self, event: dict[str, Any]) -> None:
        self._requests.post(self._table_endpoint("jarvis_skill_events"), headers=self._headers("return=minimal"),
                            json=event, timeout=15).raise_for_status()

    def list_events(self, sprint_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        params = {"order": "occurred_at.desc", "limit": str(max(1, min(int(limit), 1000)))}
        if sprint_id:
            params["sprint_id"] = f"eq.{sprint_id}"
        r = self._requests.get(self._table_endpoint("jarvis_skill_events"), params=params, headers=self._headers(), timeout=15)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _dict_to_sprint(x: dict[str, Any]) -> SkillSprint:
        s = SkillSprint(x["sprint_id"], x["skill_id"], x["learner_id"])
        s.state, s.hours_completed, s.version = x["state"], x["hours_completed"], x.get("version", 1)
        for e in x.get("evidence", []):
            s.evidence.append(Evidence(e["evidence_id"], e["kind"], e["title"], e["score"], e.get("metadata", {})))
        if x.get("assessment"):
            s.assessment = AssessmentResult(**x["assessment"])
        return s

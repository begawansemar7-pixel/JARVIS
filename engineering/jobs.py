"""Background engineering jobs: prepare workspace -> run engine -> commit -> report.

A job runs in a worker thread so the live voice session is never blocked. When
it finishes, `notify(text)` is called (JARVIS passes its `speak`), and the full
report is written to ~/Documents/JARVIS/Engineering/<stamp>_<slug>/:

    brief.md       the exact prompt sent to the engine
    events.ndjson  the raw engine event stream
    report.md      outcome, branch, diff stat and the engine's final report
"""
from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import EngineerConfig
from .engine import EngineResult, run_engine
from .prompt import build_prompt
from .workspace import Workspace, WorkspaceError, resolve_project, slugify

MAX_CONCURRENT_JOBS = 2


@dataclass
class Job:
    id: str
    task: str
    mode: str
    repo: Path
    report_dir: Path
    status: str = "queued"          # queued | running | succeeded | failed | cancelled
    started_at: str = ""
    finished_at: str = ""
    workspace: Workspace | None = None
    result: EngineResult | None = None
    commit: str | None = None
    changed_files: list[str] = field(default_factory=list)
    branch_removed: bool = False
    diff_stat: str = ""
    message: str = ""
    cancel: threading.Event = field(default_factory=threading.Event)


class JobManager:
    def __init__(self, config: EngineerConfig, runner=run_engine):
        self.config = config
        self.runner = runner
        self.jobs: dict[str, Job] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    # -- public API ----------------------------------------------------------
    def start(self, project_path: str, task: str, mode: str = "implement", context: str = "",
              timeout_minutes: int | None = None, notify: Callable[[str], None] | None = None,
              background: bool = True) -> Job:
        prompt = build_prompt(task, mode, context)
        repo = resolve_project(project_path, self.config.allowed_roots)
        with self._lock:
            active = [j for j in self.jobs.values() if j.status in ("queued", "running")]
            if len(active) >= MAX_CONCURRENT_JOBS:
                raise WorkspaceError(f"{len(active)} engineering jobs are already running; wait for one to finish")
            if any(j.repo == repo for j in active):
                raise WorkspaceError(f"a job is already running in {repo.name}")
            job_id = f"SE{next(self._ids)}"
            stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            job = Job(job_id, task.strip(), mode, repo,
                      self.config.report_dir / f"{stamp}_{job_id}_{slugify(task)}")
            self.jobs[job_id] = job

        # Branch + push guard are prepared synchronously so errors reach the caller.
        try:
            job.workspace = Workspace.prepare(repo, task, self.config.branch_prefix)
            minutes = max(1, min(int(timeout_minutes or self.config.default_timeout_minutes),
                                 self.config.max_timeout_minutes))
            job.report_dir.mkdir(parents=True, exist_ok=True)
            (job.report_dir / "brief.md").write_text(prompt, encoding="utf-8")
        except Exception:
            with self._lock:
                self.jobs.pop(job_id, None)
            if job.workspace is not None:
                job.workspace.remove_push_guard()
            raise

        work = lambda: self._run(job, prompt, minutes * 60, notify)  # noqa: E731
        if background:
            threading.Thread(target=work, daemon=True, name=f"engineer-{job_id}").start()
        else:
            work()
        return job

    def get(self, job_id: str | None = None) -> Job | None:
        with self._lock:
            if job_id:
                return self.jobs.get(job_id.strip().upper())
            return next(reversed(self.jobs.values()), None)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or job.status not in ("queued", "running"):
            return False
        job.cancel.set()
        return True

    # -- worker --------------------------------------------------------------
    def _run(self, job: Job, prompt: str, timeout_seconds: int, notify) -> None:
        ws = job.workspace
        job.status = "running"
        job.started_at = datetime.now().isoformat(timespec="seconds")
        try:
            job.result = self.runner(self.config, job.repo, prompt, timeout_seconds,
                                     job.report_dir / "events.ndjson", job.cancel)
            # The engine has exited: lift the guard first so it never lands in a commit.
            ws.remove_push_guard()
            job.changed_files = ws.changed_files()
            if job.mode in ("plan", "review"):
                if job.changed_files or ws.engine_commits():
                    ws.discard_changes()
                    job.message = (f"The engine changed {len(job.changed_files)} file(s) in read-only "
                                   f"{job.mode} mode; all changes were discarded.")
                job.changed_files = []
            else:
                label = "WIP (engine failed)" if not job.result.ok else "JARVIS"
                job.commit = ws.commit_changes(f"{label}: {job.task[:60]}\n\n{job.task}\n\n"
                                               f"Engine: jcode ({self.config.provider})")
                job.diff_stat = ws.diff_stat()
            if not job.commit and not job.changed_files:
                job.branch_removed = ws.return_to_base()
            if job.cancel.is_set():
                job.status = "cancelled"
            else:
                job.status = "succeeded" if job.result.ok else "failed"
        except Exception as e:  # never let a worker die silently
            job.status = "failed"
            job.message = f"{type(e).__name__}: {e}"[:500]
        finally:
            ws.remove_push_guard()
            job.finished_at = datetime.now().isoformat(timespec="seconds")
            try:
                self._write_report(job)
            except OSError:
                pass
        if notify:
            try:
                notify(self.announcement(job))
            except Exception:
                pass

    # -- rendering -----------------------------------------------------------
    def summary(self, job: Job) -> str:
        r = job.result
        lines = [f"Job {job.id} ({job.mode}) in {job.repo.name}: {job.status}."]
        if job.workspace and job.branch_removed:
            lines.append(f"Nothing was kept, so JARVIS returned to {job.workspace.base_branch} and removed "
                         f"the work branch.")
        elif job.workspace:
            lines.append(f"Branch: {job.workspace.work_branch} (from {job.workspace.base_branch}).")
        if job.status in ("queued", "running"):
            lines.append("Still working.")
            return " ".join(lines)
        if job.commit:
            lines.append(f"Committed {job.commit} with {len(job.changed_files)} changed file(s).")
        elif job.mode == "implement":
            lines.append("No files were changed.")
        if job.message:
            lines.append(job.message)
        if r and r.error:
            lines.append(f"Engine error: {r.error[:300]}")
        if r and r.tools_used:
            lines.append("Tools: " + ", ".join(f"{k}×{v}" for k, v in sorted(r.tools_used.items())) + ".")
        lines.append(f"Report: {job.report_dir / 'report.md'}")
        return " ".join(lines)

    def announcement(self, job: Job) -> str:
        final = (job.result.text.strip() if job.result else "")[:1500]
        return (
            "[ENGINEERING_JOB] A background software engineering job just finished. Tell the user "
            "in 2-3 short sentences what happened, in their language, and mention the branch. Do not "
            "read file paths or code aloud.\n" + self.summary(job)
            + (f"\nEngine final report (excerpt):\n{final}" if final else "")
        )

    def _write_report(self, job: Job) -> None:
        r = job.result
        ws = job.workspace
        lines = [
            f"# Engineering job {job.id} — {job.status}", "",
            f"- Task: {job.task}",
            f"- Mode: {job.mode}",
            f"- Repository: {job.repo}",
            f"- Branch: {ws.work_branch if ws else '-'} (base {ws.base_branch if ws else '-'} @ "
            f"{ws.base_commit[:10] if ws else '-'})",
            f"- Commit: {job.commit or '-'}",
            f"- Started / finished: {job.started_at} / {job.finished_at}",
        ]
        if r:
            lines += [f"- Engine session: {r.session_id or '-'}", f"- Duration: {r.duration_seconds}s",
                      f"- Exit code: {r.exit_code}", f"- Tool errors: {r.tool_errors}"]
        if job.message:
            lines += ["", f"**{job.message}**"]
        if r and r.error:
            lines += ["", "## Engine error", "", "```", r.error, "```"]
        if job.diff_stat:
            lines += ["", "## Diff stat", "", "```", job.diff_stat, "```"]
        lines += ["", "## Review and merge", "", "```bash",
                  f"git -C '{job.repo}' diff {ws.base_branch if ws else ''}...{ws.work_branch if ws else ''}",
                  f"git -C '{job.repo}' switch {ws.base_branch if ws else ''} && "
                  f"git -C '{job.repo}' merge {ws.work_branch if ws else ''}", "```"]
        if r and r.text:
            lines += ["", "## Engine final report", "", r.text]
        (job.report_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = ["Job", "JobManager"]

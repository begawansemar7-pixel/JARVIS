"""Git workspace guardrails around an autonomous coding engine.

jcode executes file edits and shell commands without asking, so JARVIS supplies
the boundary itself:

  * the project must live under a configured allowed root and be a git repo
  * the working tree must be clean, so the engine never mixes with the user's
    uncommitted work
  * work happens on a fresh `jarvis/<stamp>-<slug>` branch
  * a temporary pre-push hook refuses every push while the engine runs
  * afterwards changes are committed on that branch (or discarded in plan mode)
  * undo returns to the original branch and deletes the work branch
"""
from __future__ import annotations

import re
import subprocess
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

GUARD_MARKER = "# JARVIS_SOFTWARE_ENGINEER_PUSH_GUARD"
PUSH_GUARD = f"""#!/bin/sh
{GUARD_MARKER}
echo "JARVIS: pushing is disabled while the software engineer engine is running." >&2
exit 1
"""


class WorkspaceError(Exception):
    """The project cannot be used safely; the message is user-facing."""


def git(repo: Path, *args: str, check: bool = True, timeout: int = 60) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                            timeout=timeout, stdin=subprocess.DEVNULL)
    if check and result.returncode != 0:
        raise WorkspaceError(f"git {args[0]} failed: {result.stderr.strip()[:300]}")
    return result.stdout.strip()


def slugify(text: str, max_len: int = 40) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:max_len].rstrip("-") or "task"


def resolve_project(project_path: str, allowed_roots) -> Path:
    if not project_path or not str(project_path).strip():
        raise WorkspaceError("project_path is required")
    path = Path(str(project_path)).expanduser().resolve()
    if not path.is_dir():
        raise WorkspaceError(f"project folder not found: {path}")
    if not any(path == root or root in path.parents for root in allowed_roots):
        roots = ", ".join(str(r) for r in allowed_roots)
        raise WorkspaceError(f"{path} is outside the allowed project folders ({roots}); "
                             "add its parent to allowed_roots in config/software_engineer.json")
    try:
        top = Path(git(path, "rev-parse", "--show-toplevel")).resolve()
    except WorkspaceError:
        raise WorkspaceError(f"{path} is not a git repository; run `git init` and commit first") from None
    if not any(top == root or root in top.parents for root in allowed_roots):
        raise WorkspaceError(f"the git repository root {top} is outside the allowed project folders")
    return top


@dataclass
class Workspace:
    repo: Path
    base_branch: str
    base_commit: str
    work_branch: str
    hook_path: Path
    previous_hook: bytes | None = None
    previous_mode: int | None = None

    # -- lifecycle -----------------------------------------------------------
    @classmethod
    def prepare(cls, repo: Path, task: str, branch_prefix: str, now: datetime | None = None) -> "Workspace":
        if git(repo, "status", "--porcelain"):
            raise WorkspaceError("the working tree has uncommitted changes; commit or stash them first")
        try:
            base_commit = git(repo, "rev-parse", "HEAD")
        except WorkspaceError:
            raise WorkspaceError("the repository has no commits yet; make an initial commit first") from None
        base_branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        if base_branch == "HEAD":
            raise WorkspaceError("the repository is in detached HEAD state; check out a branch first")

        stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
        work_branch = f"{branch_prefix}{stamp}-{slugify(task)}"
        git(repo, "check-ref-format", "--branch", work_branch)
        git(repo, "switch", "-c", work_branch)

        hooks_dir = git(repo, "config", "core.hooksPath", check=False)  # e.g. husky
        if hooks_dir:
            hook_path = Path(hooks_dir).expanduser() / "pre-push"
        else:
            hook_path = Path(git(repo, "rev-parse", "--git-path", "hooks/pre-push"))
        if not hook_path.is_absolute():
            hook_path = (repo / hook_path).resolve()
        ws = cls(repo, base_branch, base_commit, work_branch, hook_path)
        ws._install_push_guard()
        return ws

    def _install_push_guard(self) -> None:
        self.hook_path.parent.mkdir(parents=True, exist_ok=True)
        if self.hook_path.exists():
            existing = self.hook_path.read_bytes()
            if GUARD_MARKER.encode() not in existing:
                self.previous_hook = existing
                self.previous_mode = self.hook_path.stat().st_mode & 0o7777
        self.hook_path.write_text(PUSH_GUARD, encoding="utf-8")
        self.hook_path.chmod(0o755)

    def remove_push_guard(self) -> None:
        if self.previous_hook is not None:
            self.hook_path.write_bytes(self.previous_hook)
            if self.previous_mode is not None:
                self.hook_path.chmod(self.previous_mode)
        elif self.hook_path.exists() and GUARD_MARKER in self.hook_path.read_text(errors="ignore"):
            self.hook_path.unlink()

    # -- results -------------------------------------------------------------
    def engine_commits(self) -> int:
        """Commits the engine made itself on the work branch (it was told not to)."""
        return int(git(self.repo, "rev-list", "--count", f"{self.base_commit}..HEAD") or 0)

    def changed_files(self) -> list[str]:
        committed = git(self.repo, "diff", "--name-only", self.base_commit, "HEAD").splitlines()
        # -z output is NUL-separated and never trimmed, so "XY path" columns stay aligned.
        raw = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain", "-z",
                              "--untracked-files=all"], capture_output=True, text=True, timeout=60,
                             stdin=subprocess.DEVNULL).stdout
        pending, entries, i = [], raw.split("\0"), 0
        while i < len(entries):
            entry = entries[i]
            if len(entry) > 3:
                pending.append(entry[3:])
                if entry[0] in "RC":   # renames/copies carry the source path as the next entry
                    i += 1
            i += 1
        return sorted(set(committed) | set(pending))

    def commit_changes(self, message: str) -> str | None:
        git(self.repo, "add", "-A")
        if not git(self.repo, "diff", "--cached", "--name-only"):
            return None
        identity = []
        if not git(self.repo, "config", "user.email", check=False):
            identity = ["-c", "user.name=JARVIS", "-c", "user.email=jarvis@localhost"]
        git(self.repo, *identity, "commit", "--no-verify", "-m", message)
        return git(self.repo, "rev-parse", "--short", "HEAD")

    def diff_stat(self) -> str:
        return git(self.repo, "diff", "--stat", self.base_commit, "HEAD", check=False)

    def discard_changes(self) -> None:
        """Plan mode only: drop everything the engine touched on the work branch."""
        git(self.repo, "reset", "--hard", self.base_commit)
        git(self.repo, "clean", "-fd")

    def branch_exists(self) -> bool:
        return bool(git(self.repo, "branch", "--list", self.work_branch, check=False))

    def return_to_base(self) -> bool:
        """Delete an empty work branch (no changes kept). Returns True when cleaned up."""
        if git(self.repo, "rev-parse", "--abbrev-ref", "HEAD", check=False) != self.work_branch:
            return False
        if git(self.repo, "status", "--porcelain") or self.engine_commits():
            return False
        git(self.repo, "switch", self.base_branch)
        git(self.repo, "branch", "-D", self.work_branch)
        return True

    def abandon(self) -> str:
        """Undo: back to the base branch and delete the work branch.

        Never discards uncommitted work: if the user has edits in the tree, the
        undo refuses instead of resetting anything."""
        self.remove_push_guard()
        if not self.branch_exists():
            return f"Nothing to undo: {self.work_branch} no longer exists."
        current = git(self.repo, "rev-parse", "--abbrev-ref", "HEAD", check=False)
        if current == self.work_branch:
            if git(self.repo, "status", "--porcelain"):
                raise WorkspaceError(f"{self.work_branch} has uncommitted edits; commit or stash them "
                                     "before undoing")
            git(self.repo, "switch", self.base_branch)
        git(self.repo, "branch", "-D", self.work_branch)
        return f"Returned to {self.base_branch} and deleted {self.work_branch}."


__all__ = ["Workspace", "WorkspaceError", "git", "resolve_project", "slugify"]

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from actions import software_engineer as action
from core import undo
from core.action_loader import _validate
from engineering.config import parse_config
from engineering.engine import EngineResult, build_command, parse_event, run_engine
from engineering.jobs import JobManager
from engineering.prompt import build_prompt
from engineering.workspace import GUARD_MARKER, Workspace, WorkspaceError, git, resolve_project

FAKE_JCODE = textwrap.dedent("""\
    #!{python}
    import json, os, subprocess, sys, time
    mode = os.environ.get("FAKE_JCODE_MODE", "edit")
    def emit(**event):
        print(json.dumps(event), flush=True)
    if "--version" in sys.argv:
        print("jcode 0.84.0-fake"); sys.exit(0)
    emit(type="start", session_id="sess-1")
    emit(type="tool_start", id="1", name="apply_patch")
    if mode in ("edit", "plan_edit", "commit"):
        with open("feature.py", "w") as f:
            f.write("def answer():\\n    return 42\\n")
    if mode == "commit":
        subprocess.run(["git", "-c", "user.name=x", "-c", "user.email=x@x", "add", "-A"])
        subprocess.run(["git", "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qm", "engine"])
    if mode == "push":
        r = subprocess.run(["git", "push", "origin", "HEAD"], capture_output=True, text=True)
        with open("push_result.txt", "w") as f:
            f.write(str(r.returncode))
    if mode == "sleep":
        time.sleep(120)
    if mode == "fail":
        emit(type="error", session_id="sess-1", message="provider auth failed")
        sys.exit(1)
    emit(type="tool_done", id="1", name="apply_patch", output="ok", error=None)
    emit(type="done", session_id="sess-1", text="## Summary\\nAdded answer().", usage={{"input": 10}})
""")


@pytest.fixture
def root(tmp_path):
    return (tmp_path / "Projects").resolve()


@pytest.fixture
def repo(root):
    path = root / "demo"
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    (path / "README.md").write_text("demo\n")
    git(path, "add", "-A")
    git(path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    return path


@pytest.fixture
def config(tmp_path, root, monkeypatch):
    binary = tmp_path / "bin" / "jcode"
    binary.parent.mkdir()
    binary.write_text(FAKE_JCODE.format(python=sys.executable))
    binary.chmod(0o755)
    monkeypatch.setenv("JARVIS_DOCUMENTS_DIR", str(tmp_path / "Docs"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return parse_config({"binary": str(binary), "provider": "gemini", "allowed_roots": [str(root)],
                         "default_timeout_minutes": 1, "max_timeout_minutes": 2})


def test_config_validation(root):
    with pytest.raises(ValueError):
        parse_config({"allowed_roots": []})
    with pytest.raises(ValueError):
        parse_config({"engine": "other", "allowed_roots": [str(root)]})


def test_repository_config_loads():
    from engineering.config import load_config
    cfg = load_config()
    assert cfg.provider == "gemini" and cfg.branch_prefix == "jarvis/"


def test_project_must_be_inside_allowed_roots_and_a_repo(tmp_path, root, repo):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    with pytest.raises(WorkspaceError, match="outside"):
        resolve_project(str(outside), (root,))
    plain = root / "not-git"
    plain.mkdir()
    with pytest.raises(WorkspaceError, match="not a git repository"):
        resolve_project(str(plain), (root,))
    assert resolve_project(str(repo / "."), (root,)) == repo


def test_dirty_tree_is_refused(repo):
    (repo / "README.md").write_text("changed\n")
    with pytest.raises(WorkspaceError, match="uncommitted"):
        Workspace.prepare(repo, "task", "jarvis/")


def test_prompt_contains_rules_and_mode():
    implement = build_prompt("Add login", "implement")
    assert "Do not run `git push`" in implement and "## Verification" in implement
    assert "READ ONLY" in build_prompt("Plan it", "plan")
    with pytest.raises(ValueError):
        build_prompt("", "implement")
    with pytest.raises(ValueError):
        build_prompt("x", "yolo")


def test_command_and_event_parsing(config, repo):
    cmd = build_command("jcode", config, repo, "do it")
    assert cmd[:2] == ["jcode", "--no-update"] and cmd[-3:] == ["run", "--ndjson", "do it"]
    assert ["-C", str(repo)] == cmd[3:5] and ["-p", "gemini"] == cmd[5:7]
    result = EngineResult(ok=False)
    for line in ['{"type":"start","session_id":"s"}', "garbage",
                 '{"type":"tool_start","name":"bash"}', '{"type":"tool_done","name":"bash","error":"x"}',
                 '{"type":"done","text":"final","usage":{"input":1}}']:
        parse_event(line, result)
    assert result.ok and result.text == "final" and result.tools_used == {"bash": 1} and result.tool_errors == 1


def test_implement_job_commits_on_work_branch_and_undo_restores(config, repo, tmp_path):
    undo.clear()
    messages = []
    manager = JobManager(config)
    job = manager.start(str(repo), "Add answer function", notify=messages.append, background=False)
    assert job.status == "succeeded", job.message
    assert job.workspace.work_branch.startswith("jarvis/")
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == job.workspace.work_branch
    assert job.commit and job.changed_files == ["feature.py"]
    assert git(repo, "status", "--porcelain") == ""
    assert not job.workspace.hook_path.exists()                  # guard removed afterwards
    report = (job.report_dir / "report.md").read_text()
    assert "Added answer()" in report and "feature.py" in report
    assert (job.report_dir / "events.ndjson").read_text().count("\n") >= 4
    assert messages and messages[0].startswith("[ENGINEERING_JOB]")

    assert "Returned to main" in job.workspace.abandon()
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert not (repo / "feature.py").exists()
    assert job.workspace.work_branch not in git(repo, "branch")


def test_push_is_blocked_while_engine_runs(config, repo, tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    git(repo, "remote", "add", "origin", str(remote))
    monkeypatch.setenv("FAKE_JCODE_MODE", "push")
    job = JobManager(config).start(str(repo), "try to push", background=False)
    assert git(repo, "show", f"{job.commit}:push_result.txt") != "0"
    assert git(remote, "branch") == ""                           # nothing reached the remote


def test_existing_pre_push_hook_is_restored(config, repo):
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\nexit 0\n")
    JobManager(config).start(str(repo), "task", background=False)
    assert hook.read_text() == "#!/bin/sh\nexit 0\n" and GUARD_MARKER not in hook.read_text()


def test_plan_mode_discards_engine_changes(config, repo, monkeypatch):
    monkeypatch.setenv("FAKE_JCODE_MODE", "plan_edit")
    job = JobManager(config).start(str(repo), "plan the feature", mode="plan", background=False)
    assert "discarded" in job.message
    assert not (repo / "feature.py").exists() and job.commit is None


def test_engine_self_commit_is_kept_on_branch_in_implement_mode(config, repo, monkeypatch):
    monkeypatch.setenv("FAKE_JCODE_MODE", "commit")
    job = JobManager(config).start(str(repo), "task", background=False)
    assert job.changed_files == ["feature.py"]
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == job.workspace.work_branch


def test_engine_failure_is_reported(config, repo, monkeypatch):
    monkeypatch.setenv("FAKE_JCODE_MODE", "fail")
    job = JobManager(config).start(str(repo), "task", background=False)
    assert job.status == "failed" and "provider auth failed" in job.result.error
    assert "Engine error" in (job.report_dir / "report.md").read_text()


def test_timeout_kills_engine(config, repo, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_JCODE_MODE", "sleep")
    started = time.monotonic()
    result = run_engine(config, repo, "x", timeout_seconds=2, event_log=tmp_path / "ev.ndjson")
    assert result.timed_out and not result.ok and time.monotonic() - started < 30


def test_one_job_per_repository(config, repo, monkeypatch):
    monkeypatch.setenv("FAKE_JCODE_MODE", "sleep")
    manager = JobManager(config)
    job = manager.start(str(repo), "long task")
    try:
        with pytest.raises(WorkspaceError, match="already running"):
            manager.start(str(repo), "second task")
    finally:
        manager.cancel(job.id)
        deadline = time.monotonic() + 30
        while job.status in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(0.2)
    assert job.status == "cancelled"


def test_failed_prepare_does_not_leave_a_phantom_job(config, repo):
    (repo / "README.md").write_text("dirty\n")
    manager = JobManager(config)
    with pytest.raises(WorkspaceError):
        manager.start(str(repo), "task")
    assert manager.jobs == {}


def test_action_contract_and_flow(config, repo, monkeypatch):
    assert _validate(action, "software_engineer.py").valid
    manager = JobManager(config)
    monkeypatch.setattr(action, "_get_manager", lambda: manager)
    assert "jcode ready (jcode 0.84.0-fake)" in action.software_engineer({"operation": "status"})

    spoken = []
    out = action.software_engineer({"operation": "start", "project_path": str(repo),
                                    "task": "Add answer function"}, speak=spoken.append)
    assert out.startswith("Started engineering job SE1")
    deadline = time.monotonic() + 30
    while not spoken and time.monotonic() < deadline:
        time.sleep(0.2)
    assert spoken and "succeeded" in spoken[0]
    assert "Added answer()" in action.software_engineer({"operation": "job"})

    undo.clear()
    manager2 = JobManager(config)
    monkeypatch.setattr(action, "_get_manager", lambda: manager2)
    git(repo, "switch", "-q", "main")
    out = action.software_engineer({"operation": "start", "project_path": str(repo / "missing")})
    assert out.startswith("Engineering job not started")


def test_missing_engine_gives_install_guidance(config, repo, monkeypatch):
    missing = parse_config({"binary": "/nonexistent/jcode", "allowed_roots": [str(repo.parent)]})
    monkeypatch.setattr(action, "_get_manager", lambda: JobManager(missing))
    monkeypatch.setenv("HOME", str(repo.parent))   # hide any real ~/.local/bin/jcode
    out = action.software_engineer({"operation": "start", "project_path": str(repo), "task": "x"})
    assert "not installed" in out and "brew install jcode" in out


def test_push_guard_honours_core_hooks_path(config, repo, tmp_path, monkeypatch):
    git(repo, "config", "core.hooksPath", ".husky")
    (repo / ".husky").mkdir()
    (repo / ".husky" / "pre-push").write_text("#!/bin/sh\nexit 0\n")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "husky")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    git(repo, "remote", "add", "origin", str(remote))
    monkeypatch.setenv("FAKE_JCODE_MODE", "push")
    job = JobManager(config).start(str(repo), "try to push", background=False)
    assert git(remote, "branch") == ""
    assert git(repo, "show", f"{job.commit}:push_result.txt") != "0"
    assert (repo / ".husky" / "pre-push").read_text() == "#!/bin/sh\nexit 0\n"
    assert job.changed_files == ["push_result.txt"]
    assert git(repo, "show", "--name-only", "--format=", job.commit) == "push_result.txt"


def test_changed_files_parses_paths_exactly(repo):
    ws = Workspace.prepare(repo, "task", "jarvis/")
    try:
        (repo / "README.md").write_text("modified\n")
        (repo / ".hidden").mkdir()
        (repo / ".hidden" / "new file.txt").write_text("x")
        git(repo, "mv", "README.md", "DOCS.md")
        assert ws.changed_files() == [".hidden/new file.txt", "DOCS.md"]
    finally:
        ws.remove_push_guard()


def test_engine_env_opts_out_of_telemetry_and_caps_turns(config, monkeypatch):
    from engineering.engine import engine_env
    monkeypatch.delenv("JCODE_NO_TELEMETRY", raising=False)
    env = engine_env(config)
    assert env["JCODE_NO_TELEMETRY"] == "1"
    assert env["JCODE_RUN_AUTO_POKE_MAX_TURNS"] == str(config.max_turns)
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_read_only_job_returns_to_base_and_removes_branch(config, repo, monkeypatch):
    monkeypatch.setenv("FAKE_JCODE_MODE", "plan_edit")
    job = JobManager(config).start(str(repo), "plan it", mode="plan", background=False)
    assert job.branch_removed
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert git(repo, "branch", "--list", "jarvis/*") == ""
    assert "Nothing to undo" in job.workspace.abandon()


def test_failed_job_without_changes_cleans_branch_and_explains_signature_error(config, repo, tmp_path):
    fake = tmp_path / "bin" / "jcode"
    fake.write_text(FAKE_JCODE.format(python=sys.executable).replace(
        'message="provider auth failed"',
        'message="Gemini request failed (HTTP 400): Function call is missing a thought_signature"'))
    import os
    os.environ["FAKE_JCODE_MODE"] = "fail"
    try:
        job = JobManager(config).start(str(repo), "task", background=False)
    finally:
        del os.environ["FAKE_JCODE_MODE"]
    assert job.status == "failed" and job.branch_removed
    assert job.result.error.startswith("jcode cannot currently run tools with Gemini 3 models")
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"

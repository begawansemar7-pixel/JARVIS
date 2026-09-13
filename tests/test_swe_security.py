from pathlib import Path

import pytest

from engineering.swe_agent import _safe_command, _validate_relative_path


def test_safe_command_allows_python_and_rewrites_executable():
    parts = _safe_command("python -m pytest -q")
    assert Path(parts[0]).name.startswith("python")
    assert parts[1:3] == ["-m", "pytest"]


def test_safe_command_rejects_shell_injection():
    with pytest.raises(ValueError):
        _safe_command("python -m pytest -q && cat config/api_keys.json")


def test_safe_command_rejects_non_allowlisted_executable():
    with pytest.raises(ValueError):
        _safe_command("bash -c 'echo unsafe'")


def test_validate_relative_path_rejects_escape(tmp_path: Path):
    with pytest.raises(ValueError):
        _validate_relative_path(tmp_path, "../outside.txt")


def test_validate_relative_path_accepts_nested_file(tmp_path: Path):
    target = _validate_relative_path(tmp_path, "src/app.py")
    assert target == (tmp_path / "src/app.py").resolve()

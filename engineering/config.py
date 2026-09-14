"""Loader for config/software_engineer.json."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "software_engineer.json"
ENV_DOCUMENTS_DIR = "JARVIS_DOCUMENTS_DIR"


@dataclass(frozen=True)
class EngineerConfig:
    binary: str
    provider: str
    model: str
    allowed_roots: tuple[Path, ...]
    default_timeout_minutes: int
    max_timeout_minutes: int
    max_turns: int
    branch_prefix: str
    report_dir: Path


def _path(value: str) -> Path:
    return Path(os.path.expanduser(value)).resolve()


def parse_config(raw: dict) -> EngineerConfig:
    if raw.get("engine", "jcode") != "jcode":
        raise ValueError("only the 'jcode' engine is supported")
    roots = tuple(_path(r) for r in raw.get("allowed_roots", []) if str(r).strip())
    if not roots:
        raise ValueError("allowed_roots must list at least one folder")
    default_timeout = int(raw.get("default_timeout_minutes", 20))
    max_timeout = int(raw.get("max_timeout_minutes", 60))
    if not 1 <= default_timeout <= max_timeout:
        raise ValueError("expected 1 ≤ default_timeout_minutes ≤ max_timeout_minutes")
    prefix = str(raw.get("branch_prefix", "jarvis/")).strip() or "jarvis/"

    override = os.environ.get(ENV_DOCUMENTS_DIR)
    report_dir = (_path(override) / "Engineering") if override else _path(
        raw.get("report_dir", "~/Documents/JARVIS/Engineering"))
    return EngineerConfig(
        binary=str(raw.get("binary") or "jcode"),
        provider=str(raw.get("provider") or "auto"),
        model=str(raw.get("model") or ""),
        allowed_roots=roots,
        default_timeout_minutes=default_timeout,
        max_timeout_minutes=max_timeout,
        max_turns=max(1, int(raw.get("max_turns", 8))),
        branch_prefix=prefix if prefix.endswith("/") else prefix + "/",
        report_dir=report_dir,
    )


def load_config(path: Path = CONFIG_PATH) -> EngineerConfig:
    with open(path, "r", encoding="utf-8") as f:
        return parse_config(json.load(f))


__all__ = ["EngineerConfig", "load_config", "parse_config"]

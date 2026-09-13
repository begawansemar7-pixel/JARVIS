"""Loader for config/private_brain.json.

The JSON file is the single source of truth for Private Brain policy. Anything
that would weaken the boundary silently (unknown levels, content logging) is
rejected with ValueError instead of being ignored.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .private_brain import AccessContext, Classification

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "private_brain.json"


@dataclass(frozen=True)
class PrivateBrainConfig:
    default_classification: Classification
    max_cloud_classification: Classification
    private_runtime_required_for: frozenset[Classification]
    require_role_match_when_roles_are_declared: bool
    log_access_decisions: bool
    principal: AccessContext
    vault_dir: Path
    audit_log: Path
    keychain_service: str


def _resolve(path: str, base: Path) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else base / p


def parse_config(raw: dict, base_dir: Path = BASE_DIR) -> PrivateBrainConfig:
    levels = raw.get("classification_levels")
    expected = {c.name: c.value for c in Classification}
    if levels != expected:
        raise ValueError(f"classification_levels must be exactly {expected}")

    if raw.get("log_content", False) is not False:
        raise ValueError("log_content=true is not supported: audit logs never contain document content")

    principal = raw.get("local_principal") or {}
    storage = raw.get("storage") or {}
    return PrivateBrainConfig(
        default_classification=Classification.parse(raw.get("default_classification", "INTERNAL")),
        max_cloud_classification=Classification.parse(raw.get("max_cloud_classification", "CONFIDENTIAL")),
        private_runtime_required_for=frozenset(
            Classification.parse(v) for v in raw.get("private_runtime_required_for", [])
        ),
        require_role_match_when_roles_are_declared=bool(
            raw.get("require_role_match_when_roles_are_declared", True)
        ),
        log_access_decisions=bool(raw.get("log_access_decisions", True)),
        principal=AccessContext(
            subject=str(principal.get("subject", "owner")),
            roles=frozenset(str(r) for r in principal.get("roles", [])),
            clearance=Classification.parse(principal.get("clearance", "INTERNAL")),
        ),
        vault_dir=_resolve(storage.get("vault_dir", "memory/private_brain/vault"), base_dir),
        audit_log=_resolve(storage.get("audit_log", "memory/private_brain/audit.jsonl"), base_dir),
        keychain_service=str(storage.get("keychain_service", "jarvis.private_brain")),
    )


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> PrivateBrainConfig:
    with Path(path).open("r", encoding="utf-8") as f:
        return parse_config(json.load(f))


__all__ = ["DEFAULT_CONFIG_PATH", "PrivateBrainConfig", "load_config", "parse_config"]

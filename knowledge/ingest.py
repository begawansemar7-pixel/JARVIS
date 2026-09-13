"""Secure document ingestion primitives for Private Brain."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

LEVELS = {"PUBLIC": 0, "INTERNAL": 1, "CONFIDENTIAL": 2, "SECRET": 3, "TOP_SECRET": 4}

@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    filename: str
    classification: str
    owner: str
    allowed_roles: tuple[str, ...]
    content_hash: str
    content: str


def classify(label: str | None) -> str:
    value = (label or "INTERNAL").upper().replace("-", "_")
    if value not in LEVELS:
        raise ValueError(f"Unknown classification: {label}")
    return value


def ingest_text(path: str | Path, *, owner: str, classification: str = "INTERNAL", allowed_roles: tuple[str, ...] = ()) -> DocumentRecord:
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    document_id = f"doc-{digest[:16]}"
    return DocumentRecord(document_id, p.name, classify(classification), owner, tuple(allowed_roles), digest, raw)

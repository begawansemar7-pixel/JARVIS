"""Secure document ingestion primitives for Private Brain."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .private_brain import Classification

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    filename: str
    classification: str
    owner: str
    allowed_roles: tuple[str, ...]
    content_hash: str
    content: str


def classify(label: str | None, default: str = "INTERNAL") -> str:
    return Classification.parse(label or default).name


def ingest_text(
    path: str | Path,
    *,
    owner: str,
    classification: str | None = None,
    allowed_roles: tuple[str, ...] = (),
    default_classification: str = "INTERNAL",
) -> DocumentRecord:
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"not a file: {p.name}")
    if p.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError(f"document exceeds {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB")
    try:
        raw = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ValueError("only UTF-8 text documents are supported") from None
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    document_id = f"doc-{digest[:16]}"
    return DocumentRecord(
        document_id, p.name, classify(classification, default_classification),
        owner, tuple(allowed_roles), digest, raw,
    )

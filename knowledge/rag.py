"""ACL-aware retrieval primitives for JARVIS Private Brain.

This module deliberately keeps the storage backend abstract. Retrieval results are
filtered by classification and role *before* they are returned as LLM context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

LEVELS = {"PUBLIC": 0, "INTERNAL": 1, "CONFIDENTIAL": 2, "SECRET": 3, "TOP_SECRET": 4}

@dataclass(frozen=True)
class KnowledgeChunk:
    document_id: str
    content: str
    classification: str = "INTERNAL"
    allowed_roles: frozenset[str] = field(default_factory=frozenset)
    source: str | None = None
    score: float = 0.0

@dataclass(frozen=True)
class Principal:
    subject: str
    role: str
    clearance: str = "INTERNAL"


def authorized(principal: Principal, chunk: KnowledgeChunk) -> bool:
    """Return whether a principal may receive this chunk as model context."""
    if LEVELS.get(principal.clearance, -1) < LEVELS.get(chunk.classification, 99):
        return False
    if chunk.allowed_roles and principal.role not in chunk.allowed_roles:
        return False
    return True


def filter_context(principal: Principal, chunks: Iterable[KnowledgeChunk]) -> list[KnowledgeChunk]:
    """Apply deny-by-default authorization before LLM context assembly."""
    return [c for c in chunks if authorized(principal, c)]


def build_context(principal: Principal, chunks: Iterable[KnowledgeChunk], max_chunks: int = 8) -> str:
    """Build minimal RAG context from authorized chunks only."""
    allowed = sorted(filter_context(principal, chunks), key=lambda c: c.score, reverse=True)
    allowed = allowed[:max_chunks]
    return "\n\n---\n\n".join(c.content for c in allowed)

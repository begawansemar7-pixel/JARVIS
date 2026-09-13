"""JARVIS Private Brain / Confidential Knowledge Fabric.

Policy-first local knowledge vault primitives. This module intentionally does not
send documents to an LLM. It provides classification, authorization, metadata,
and a safe retrieval boundary that an adapter can connect to a vector store.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from hashlib import sha256
from typing import Iterable, Mapping


class Classification(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    SECRET = 3
    TOP_SECRET = 4


@dataclass(frozen=True)
class AccessContext:
    subject: str
    roles: frozenset[str] = frozenset()
    clearance: Classification = Classification.INTERNAL


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    title: str
    classification: Classification
    owner: str
    allowed_roles: frozenset[str] = frozenset()
    content_hash: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_text(
        cls,
        document_id: str,
        title: str,
        text: str,
        classification: Classification,
        owner: str,
        allowed_roles: Iterable[str] = (),
        metadata: Mapping[str, str] | None = None,
    ) -> "KnowledgeDocument":
        digest = sha256(text.encode("utf-8")).hexdigest()
        return cls(
            document_id=document_id,
            title=title,
            classification=classification,
            owner=owner,
            allowed_roles=frozenset(allowed_roles),
            content_hash=digest,
            metadata=dict(metadata or {}),
        )


def can_read(document: KnowledgeDocument, context: AccessContext) -> bool:
    """Apply clearance and role checks before any content reaches an LLM."""
    if context.clearance < document.classification:
        return False
    if document.allowed_roles and not (context.roles & document.allowed_roles):
        return False
    return True


def filter_authorized(
    documents: Iterable[KnowledgeDocument], context: AccessContext
) -> list[KnowledgeDocument]:
    return [doc for doc in documents if can_read(doc, context)]


class ConfidentialKnowledgePolicy:
    """Central policy boundary for Private Brain integrations."""

    def __init__(self, max_cloud_classification: Classification = Classification.CONFIDENTIAL):
        self.max_cloud_classification = max_cloud_classification

    def allow_cloud_context(self, document: KnowledgeDocument) -> bool:
        return document.classification <= self.max_cloud_classification

    def require_private_runtime(self, document: KnowledgeDocument) -> bool:
        return document.classification > self.max_cloud_classification


__all__ = [
    "AccessContext",
    "Classification",
    "ConfidentialKnowledgePolicy",
    "KnowledgeDocument",
    "can_read",
    "filter_authorized",
]

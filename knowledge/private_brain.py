"""JARVIS Private Brain / Confidential Knowledge Fabric.

Policy-first local knowledge vault primitives. This module intentionally does not
send documents to an LLM. It provides classification, authorization, metadata,
and a safe retrieval boundary that an adapter can connect to a vector store.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from hashlib import sha256
from typing import TYPE_CHECKING, Iterable, Mapping

from .audit import AccessEvent

if TYPE_CHECKING:  # pragma: no cover
    from .audit import AuditLogger
    from .config import PrivateBrainConfig


class Classification(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    SECRET = 3
    TOP_SECRET = 4

    @classmethod
    def parse(cls, value: "str | Classification") -> "Classification":
        """Parse a label such as 'confidential' or 'top-secret'. Raises ValueError."""
        if isinstance(value, Classification):
            return value
        name = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls[name]
        except KeyError:
            raise ValueError(f"Unknown classification: {value!r}") from None


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


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str


def evaluate_access(
    document: KnowledgeDocument, context: AccessContext, *, require_role_match: bool = True
) -> AccessDecision:
    """Apply clearance and role checks before any content reaches an LLM."""
    if context.clearance < document.classification:
        return AccessDecision(False, "insufficient_clearance")
    if require_role_match and document.allowed_roles and not (context.roles & document.allowed_roles):
        return AccessDecision(False, "role_not_permitted")
    return AccessDecision(True, "granted")


def can_read(
    document: KnowledgeDocument, context: AccessContext, *, require_role_match: bool = True
) -> bool:
    return evaluate_access(document, context, require_role_match=require_role_match).allowed


def filter_authorized(
    documents: Iterable[KnowledgeDocument],
    context: AccessContext,
    *,
    require_role_match: bool = True,
    audit: "AuditLogger | None" = None,
    action: str = "read",
) -> list[KnowledgeDocument]:
    """Return only readable documents; every decision is sent to `audit` when given."""
    allowed = []
    for doc in documents:
        decision = evaluate_access(doc, context, require_role_match=require_role_match)
        if audit is not None:
            audit.record(AccessEvent.now(
                context.subject, doc.document_id, action,
                "allow" if decision.allowed else "deny", decision.reason,
                classification=doc.classification.name,
            ))
        if decision.allowed:
            allowed.append(doc)
    return allowed


class ConfidentialKnowledgePolicy:
    """Central policy boundary for Private Brain integrations."""

    def __init__(
        self,
        max_cloud_classification: Classification = Classification.CONFIDENTIAL,
        private_runtime_required_for: Iterable[Classification] = (),
    ):
        self.max_cloud_classification = max_cloud_classification
        self.private_runtime_required_for = frozenset(private_runtime_required_for)

    @classmethod
    def from_config(cls, config: "PrivateBrainConfig") -> "ConfidentialKnowledgePolicy":
        return cls(config.max_cloud_classification, config.private_runtime_required_for)

    def allow_cloud_context(self, document: KnowledgeDocument) -> bool:
        return not self.require_private_runtime(document)

    def require_private_runtime(self, document: KnowledgeDocument) -> bool:
        return (
            document.classification > self.max_cloud_classification
            or document.classification in self.private_runtime_required_for
        )


__all__ = [
    "AccessContext",
    "AccessDecision",
    "Classification",
    "ConfidentialKnowledgePolicy",
    "KnowledgeDocument",
    "can_read",
    "evaluate_access",
    "filter_authorized",
]

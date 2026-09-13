"""JARVIS Private Brain / Confidential Knowledge Fabric."""

from .private_brain import (
    AccessContext,
    Classification,
    ConfidentialKnowledgePolicy,
    KnowledgeDocument,
    can_read,
    filter_authorized,
)
from .ingest import DocumentRecord, ingest_text
from .rag import KnowledgeChunk, Principal, authorized, build_context, filter_context
from .gateway import route

__all__ = [
    "AccessContext", "Classification", "ConfidentialKnowledgePolicy",
    "KnowledgeDocument", "can_read", "filter_authorized",
    "DocumentRecord", "ingest_text", "KnowledgeChunk", "Principal",
    "authorized", "build_context", "filter_context", "route",
]

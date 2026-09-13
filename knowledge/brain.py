"""Private Brain service: encrypted storage + ACL-filtered, cloud-bounded retrieval.

Flow for every search:

    ACL filter (metadata only) -> decrypt / extract authorized docs locally
    -> chunk & score -> cloud boundary (gateway.route) -> provenance-tagged excerpts

Documents come from two places: the encrypted vault (ingested copies, with an
encrypted index) and configured reference folders, which are read in place.
Nothing in this module logs content, titles or queries.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .audit import AccessEvent, AuditLogger
from .config import PrivateBrainConfig, load_config
from .gateway import route
from .ingest import ingest_text
from .keys import load_vault_key
from .private_brain import AccessContext, Classification, KnowledgeDocument, filter_authorized
from .rag import KnowledgeChunk
from .reference import ExtractionError, ReferenceLibrary, is_reference
from .vault import EncryptedVault

INDEX_ID = "_index"
CHUNK_CHARS = 700
_WORD_RE = re.compile(r"\w{3,}", re.UNICODE)


@dataclass(frozen=True)
class SearchHit:
    document: KnowledgeDocument
    chunk: KnowledgeChunk


@dataclass(frozen=True)
class SearchResult:
    hits: list[SearchHit]
    withheld_private_runtime: int


def _doc_to_dict(doc: KnowledgeDocument) -> dict:
    return {
        "document_id": doc.document_id,
        "title": doc.title,
        "classification": doc.classification.name,
        "owner": doc.owner,
        "allowed_roles": sorted(doc.allowed_roles),
        "content_hash": doc.content_hash,
        "metadata": dict(doc.metadata),
    }


def _doc_from_dict(raw: dict) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id=raw["document_id"],
        title=raw["title"],
        classification=Classification.parse(raw["classification"]),
        owner=raw["owner"],
        allowed_roles=frozenset(raw.get("allowed_roles", [])),
        content_hash=raw.get("content_hash", ""),
        metadata=dict(raw.get("metadata", {})),
    )


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD_RE.findall(text)}


def _chunks(text: str) -> list[str]:
    out, buf = [], ""
    for para in (p.strip() for p in re.split(r"\n\s*\n", text)):
        if not para:
            continue
        while len(para) > CHUNK_CHARS:
            out.append(para[:CHUNK_CHARS])
            para = para[CHUNK_CHARS:]
        if buf and len(buf) + len(para) + 2 > CHUNK_CHARS:
            out.append(buf)
            buf = ""
        buf = f"{buf}\n\n{para}" if buf else para
    if buf:
        out.append(buf)
    return out


class PrivateBrain:
    def __init__(self, config: PrivateBrainConfig, vault: EncryptedVault, audit: AuditLogger):
        self.config = config
        self.vault = vault
        self.audit = audit
        self._lock = threading.RLock()
        self.references = ReferenceLibrary(config.reference_folders, owner=config.principal.subject)

    @classmethod
    def open(cls, config: PrivateBrainConfig | None = None, key: bytes | None = None) -> "PrivateBrain":
        cfg = config or load_config()
        vault = EncryptedVault(cfg.vault_dir, key or load_vault_key(cfg.keychain_service))
        return cls(cfg, vault, AuditLogger(cfg.audit_log, enabled=cfg.log_access_decisions))

    # -- index (encrypted) --------------------------------------------------
    def _load_index(self) -> dict[str, KnowledgeDocument]:
        if not (self.vault.root / f"{INDEX_ID}.enc").exists():
            return {}
        raw = json.loads(self.vault.get(INDEX_ID).decode("utf-8"))
        return {d["document_id"]: _doc_from_dict(d) for d in raw.get("documents", [])}

    def _save_index(self, index: dict[str, KnowledgeDocument]) -> None:
        payload = {"documents": [_doc_to_dict(d) for d in index.values()]}
        self.vault.put(INDEX_ID, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _all_documents(self) -> dict[str, KnowledgeDocument]:
        docs = self._load_index()
        for ref in self.references.documents():
            docs.setdefault(ref.document_id, ref)
        return docs

    def _read_text(self, doc: KnowledgeDocument) -> str:
        if is_reference(doc):
            return self.references.text(doc)
        return self.vault.get(doc.document_id).decode("utf-8")

    def _event(self, context: AccessContext, doc_id: str, action: str, decision: str,
               reason: str, classification: str = "") -> None:
        self.audit.record(AccessEvent.now(context.subject, doc_id, action, decision, reason, classification))

    def _authorized(self, context: AccessContext, docs: Iterable[KnowledgeDocument], action: str):
        return filter_authorized(
            docs, context,
            require_role_match=self.config.require_role_match_when_roles_are_declared,
            audit=self.audit, action=action,
        )

    def cloud_allowed(self, doc: KnowledgeDocument) -> bool:
        if doc.classification in self.config.private_runtime_required_for:
            return False
        try:
            return route(doc.classification, max_cloud=self.config.max_cloud_classification) == "cloud"
        except PermissionError:
            return False

    # -- operations -----------------------------------------------------------
    def ingest_file(
        self,
        path: str | Path,
        *,
        classification: str | None = None,
        allowed_roles: Iterable[str] = (),
        title: str | None = None,
        context: AccessContext | None = None,
    ) -> KnowledgeDocument:
        ctx = context or self.config.principal
        record = ingest_text(
            path, owner=ctx.subject, classification=classification,
            allowed_roles=tuple(r.strip() for r in allowed_roles if r.strip()),
            default_classification=self.config.default_classification.name,
        )
        level = Classification.parse(record.classification)
        if level > ctx.clearance:
            self._event(ctx, record.document_id, "ingest", "deny", "insufficient_clearance", level.name)
            raise PermissionError("cannot store a document above your own clearance")

        with self._lock:
            index = self._load_index()
            source = record.filename
            version = 1 + sum(1 for d in index.values() if d.metadata.get("source") == source)
            doc = KnowledgeDocument(
                document_id=record.document_id,
                title=(title or Path(source).stem).strip() or record.document_id,
                classification=level,
                owner=record.owner,
                allowed_roles=frozenset(record.allowed_roles),
                content_hash=record.content_hash,
                metadata={
                    "source": source,
                    "version": str(version),
                    "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
            )
            if doc.document_id in index:
                doc = index[doc.document_id]  # identical content already stored
            else:
                self.vault.put(doc.document_id, record.content.encode("utf-8"))
                index[doc.document_id] = doc
                self._save_index(index)
        self._event(ctx, doc.document_id, "ingest", "allow", "stored", doc.classification.name)
        return doc

    def list_documents(self, context: AccessContext | None = None) -> list[KnowledgeDocument]:
        ctx = context or self.config.principal
        with self._lock:
            docs = self._all_documents()
        return self._authorized(ctx, docs.values(), "list")

    def search(self, query: str, *, context: AccessContext | None = None, limit: int = 5) -> SearchResult:
        ctx = context or self.config.principal
        q = _tokens(query)
        if not q:
            return SearchResult([], 0)
        with self._lock:
            docs = self._all_documents()
            authorized = self._authorized(ctx, docs.values(), "search")
            scored: list[SearchHit] = []
            for doc in authorized:
                try:
                    text = self._read_text(doc)
                except ExtractionError as e:
                    self._event(ctx, doc.document_id, "retrieve", "skip", str(e), doc.classification.name)
                    continue
                for piece in _chunks(text):
                    overlap = len(q & _tokens(piece))
                    if overlap:
                        scored.append(SearchHit(doc, KnowledgeChunk(
                            doc.document_id, piece, doc.classification.name, doc.allowed_roles,
                            source=doc.metadata.get("source"), score=overlap / len(q),
                        )))
        scored.sort(key=lambda h: h.chunk.score, reverse=True)

        hits, withheld, seen_withheld = [], 0, set()
        for hit in scored:
            doc = hit.document
            if not self.cloud_allowed(doc):
                if doc.document_id not in seen_withheld:
                    seen_withheld.add(doc.document_id)
                    withheld += 1
                    self._event(ctx, doc.document_id, "retrieve", "deny",
                                "private_runtime_required", doc.classification.name)
                continue
            if len(hits) < limit:
                hits.append(hit)
        for doc_id in {h.document.document_id for h in hits}:
            self._event(ctx, doc_id, "retrieve", "allow", "cloud_context", docs[doc_id].classification.name)
        return SearchResult(hits, withheld)

    def delete(self, document_id: str, context: AccessContext | None = None) -> bool:
        ctx = context or self.config.principal
        if document_id.startswith("_"):
            raise ValueError("invalid document_id")
        with self._lock:
            index = self._load_index()
            doc = index.get(document_id)
            if doc is None:
                if document_id.startswith("ref-"):
                    raise ValueError("reference-folder files are removed by deleting them from the folder")
                return False
            if doc.owner != ctx.subject:
                self._event(ctx, document_id, "delete", "deny", "not_owner", doc.classification.name)
                raise PermissionError("only the document owner can delete it")
            self.vault.delete(document_id)
            del index[document_id]
            self._save_index(index)
        self._event(ctx, document_id, "delete", "allow", "deleted", doc.classification.name)
        return True


__all__ = ["PrivateBrain", "SearchHit", "SearchResult"]

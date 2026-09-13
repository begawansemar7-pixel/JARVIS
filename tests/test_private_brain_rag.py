from knowledge.private_brain import AccessContext, Classification, KnowledgeDocument, can_read, filter_authorized
from knowledge.rag import KnowledgeChunk, Principal, build_context


def test_clearance_blocks_higher_classification():
    doc = KnowledgeDocument("d1", "secret", Classification.SECRET, "ceo")
    assert not can_read(doc, AccessContext("u", frozenset({"Strategy"}), Classification.CONFIDENTIAL))


def test_role_acl_blocks_even_with_clearance():
    doc = KnowledgeDocument("d1", "board", Classification.CONFIDENTIAL, "ceo", frozenset({"Board"}))
    assert not can_read(doc, AccessContext("u", frozenset({"Strategy"}), Classification.TOP_SECRET))


def test_authorized_documents_are_filtered():
    docs = [
        KnowledgeDocument("public", "p", Classification.PUBLIC, "sys"),
        KnowledgeDocument("secret", "s", Classification.SECRET, "ceo"),
    ]
    result = filter_authorized(docs, AccessContext("u", frozenset(), Classification.CONFIDENTIAL))
    assert [d.document_id for d in result] == ["public"]


def test_rag_context_contains_only_authorized_chunks():
    principal = Principal("u", "Strategy", "CONFIDENTIAL")
    chunks = [
        KnowledgeChunk("d1", "PUBLIC FACT", "PUBLIC", frozenset(), score=0.9),
        KnowledgeChunk("d2", "SECRET FACT", "SECRET", frozenset(), score=1.0),
        KnowledgeChunk("d3", "STRATEGY FACT", "CONFIDENTIAL", frozenset({"Strategy"}), score=0.8),
    ]
    context = build_context(principal, chunks)
    assert "PUBLIC FACT" in context
    assert "STRATEGY FACT" in context
    assert "SECRET FACT" not in context

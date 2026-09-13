from knowledge.private_brain import (
    AccessContext,
    Classification,
    ConfidentialKnowledgePolicy,
    KnowledgeDocument,
    can_read,
    filter_authorized,
)


def make_doc(level=Classification.CONFIDENTIAL, roles=("CEO",)):
    return KnowledgeDocument.from_text(
        "DOC-1", "Strategy", "sensitive strategy", level, "CEO", roles
    )


def test_clearance_and_role_are_required():
    doc = make_doc()
    assert can_read(doc, AccessContext("henri", frozenset({"CEO"}), Classification.CONFIDENTIAL))
    assert not can_read(doc, AccessContext("analyst", frozenset({"ANALYST"}), Classification.CONFIDENTIAL))
    assert not can_read(doc, AccessContext("analyst", frozenset({"CEO"}), Classification.INTERNAL))


def test_filter_authorized_never_returns_higher_clearance_docs():
    docs = [make_doc(Classification.CONFIDENTIAL), make_doc(Classification.SECRET)]
    allowed = filter_authorized(docs, AccessContext("henri", frozenset({"CEO"}), Classification.CONFIDENTIAL))
    assert [doc.classification for doc in allowed] == [Classification.CONFIDENTIAL]


def test_hash_is_stable_and_non_reversible_metadata_only():
    doc = make_doc()
    assert len(doc.content_hash) == 64
    assert "sensitive strategy" not in doc.content_hash


def test_private_runtime_boundary():
    policy = ConfidentialKnowledgePolicy()
    assert policy.allow_cloud_context(make_doc(Classification.CONFIDENTIAL))
    assert policy.require_private_runtime(make_doc(Classification.SECRET))
    assert policy.require_private_runtime(make_doc(Classification.TOP_SECRET))

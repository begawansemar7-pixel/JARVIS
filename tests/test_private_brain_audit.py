import json
import stat

from knowledge.audit import AuditLogger
from knowledge.private_brain import AccessContext, Classification, KnowledgeDocument, filter_authorized


def docs():
    return [
        KnowledgeDocument.from_text("pub", "Public", "public body", Classification.PUBLIC, "owner"),
        KnowledgeDocument.from_text("sec", "Merger plan", "acquire rival", Classification.SECRET, "owner"),
    ]


def test_every_decision_is_logged_without_content(tmp_path):
    log = tmp_path / "audit.jsonl"
    ctx = AccessContext("henri", frozenset(), Classification.CONFIDENTIAL)
    allowed = filter_authorized(docs(), ctx, audit=AuditLogger(log), action="search")

    assert [d.document_id for d in allowed] == ["pub"]
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [(e["document_id"], e["decision"], e["reason"]) for e in events] == [
        ("pub", "allow", "granted"),
        ("sec", "deny", "insufficient_clearance"),
    ]
    text = log.read_text()
    assert "acquire rival" not in text and "Merger plan" not in text


def test_audit_file_is_owner_only(tmp_path):
    log = tmp_path / "audit.jsonl"
    filter_authorized(docs(), AccessContext("u", clearance=Classification.PUBLIC), audit=AuditLogger(log))
    assert stat.S_IMODE(log.stat().st_mode) == 0o600


def test_disabled_logger_writes_nothing(tmp_path):
    log = tmp_path / "audit.jsonl"
    filter_authorized(docs(), AccessContext("u"), audit=AuditLogger(log, enabled=False))
    assert not log.exists()

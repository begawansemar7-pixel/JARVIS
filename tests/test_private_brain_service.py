import json

import pytest
from cryptography.fernet import Fernet

from actions import private_brain as action
from core import confirm
from core.action_loader import _validate
from knowledge.brain import PrivateBrain
from knowledge.config import DEFAULT_CONFIG_PATH, parse_config
from knowledge.private_brain import AccessContext, Classification


@pytest.fixture
def brain(tmp_path):
    raw = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    raw["reference_folders"] = []  # never touch the real ~/Documents/TempJarvis in tests
    cfg = parse_config(raw, tmp_path)
    return PrivateBrain.open(cfg, key=Fernet.generate_key())


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_ingest_and_search_round_trip(brain, tmp_path):
    doc = brain.ingest_file(write(tmp_path, "strategy.md", "Fiber expansion to Kalimantan in 2027."),
                           classification="CONFIDENTIAL", title="Board strategy")
    result = brain.search("kalimantan fiber")
    assert [h.document.document_id for h in result.hits] == [doc.document_id]
    assert "Kalimantan" in result.hits[0].chunk.content
    assert doc.metadata["source"] == "strategy.md"


def test_nothing_readable_on_disk(brain, tmp_path):
    brain.ingest_file(write(tmp_path, "plan.txt", "Acquire NusantaraNet quietly."),
                      classification="CONFIDENTIAL", title="Codename Garuda")
    for path in brain.config.vault_dir.iterdir():
        blob = path.read_bytes()
        assert b"NusantaraNet" not in blob and b"Garuda" not in blob
    audit = brain.config.audit_log.read_text()
    assert "NusantaraNet" not in audit and "Garuda" not in audit


def test_secret_documents_never_reach_cloud_context(brain, tmp_path):
    brain.ingest_file(write(tmp_path, "s.txt", "merger target alpha"), classification="SECRET")
    brain.ingest_file(write(tmp_path, "c.txt", "merger budget review"), classification="CONFIDENTIAL")
    result = brain.search("merger")
    assert all("alpha" not in h.chunk.content for h in result.hits)
    assert result.withheld_private_runtime == 1
    decisions = [json.loads(l) for l in brain.config.audit_log.read_text().splitlines()]
    assert any(e["reason"] == "private_runtime_required" for e in decisions)


def test_role_acl_blocks_other_subjects(brain, tmp_path):
    brain.ingest_file(write(tmp_path, "b.txt", "board minutes dividend"),
                      classification="INTERNAL", allowed_roles=["Board"])
    analyst = AccessContext("analyst", frozenset({"Analyst"}), Classification.TOP_SECRET)
    assert brain.search("dividend", context=analyst).hits == []
    assert brain.list_documents(context=analyst) == []


def test_cannot_ingest_above_own_clearance(brain, tmp_path):
    low = AccessContext("intern", frozenset(), Classification.INTERNAL)
    with pytest.raises(PermissionError):
        brain.ingest_file(write(tmp_path, "x.txt", "text"), classification="SECRET", context=low)


def test_only_owner_can_delete(brain, tmp_path):
    doc = brain.ingest_file(write(tmp_path, "d.txt", "delete me"))
    with pytest.raises(PermissionError):
        brain.delete(doc.document_id, context=AccessContext("someone", clearance=Classification.TOP_SECRET))
    assert brain.delete(doc.document_id)
    assert brain.list_documents() == []


def test_action_contract_is_valid():
    record = _validate(action, "private_brain.py")
    assert record.valid, record.error
    assert record.name == "private_brain"


def test_action_search_withholds_secret_titles(brain, tmp_path, monkeypatch):
    monkeypatch.setattr(action, "_get_brain", lambda: brain)
    brain.ingest_file(write(tmp_path, "s.txt", "project phoenix details"),
                      classification="TOP_SECRET", title="Phoenix")
    brain.ingest_file(write(tmp_path, "i.txt", "project roadmap for phoenix team"), classification="INTERNAL")

    out = action.private_brain({"operation": "search", "query": "phoenix project"})
    assert out.startswith("[PRIVATE_BRAIN]") and len(out.splitlines()[0]) > 80
    assert "roadmap" in out and "details" not in out and "withheld" in out

    listing = action.private_brain({"operation": "list"})
    assert "Phoenix" not in listing and "titles withheld" in listing


def test_action_forget_requires_interface_confirmation(brain, tmp_path, monkeypatch):
    monkeypatch.setattr(action, "_get_brain", lambda: brain)
    monkeypatch.setattr(confirm, "_show_cb", None)
    doc = brain.ingest_file(write(tmp_path, "f.txt", "keep me"))
    out = action.private_brain({"operation": "forget", "document_id": doc.document_id})
    assert "have not done it" in out
    assert len(brain.list_documents()) == 1


def test_action_reports_locked_vault(monkeypatch):
    from knowledge.keys import KeyUnavailableError

    def locked():
        raise KeyUnavailableError("no secure OS credential store available")

    monkeypatch.setattr(action, "_get_brain", locked)
    assert "locked" in action.private_brain({"operation": "search", "query": "x"})

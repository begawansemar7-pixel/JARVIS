import json
import os

import pytest
from cryptography.fernet import Fernet

from actions import private_brain as action
from knowledge.brain import PrivateBrain
from knowledge.config import DEFAULT_CONFIG_PATH, load_config, parse_config
from knowledge.private_brain import AccessContext, Classification
from knowledge.reference import ExtractionError, extract_text


@pytest.fixture
def ref_dir(tmp_path):
    folder = tmp_path / "TempJarvis"
    folder.mkdir()
    return folder


@pytest.fixture
def brain(tmp_path, ref_dir):
    raw = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    raw["reference_folders"] = [{"path": str(ref_dir), "classification": "CONFIDENTIAL"}]
    return PrivateBrain.open(parse_config(raw, tmp_path / "base"), key=Fernet.generate_key())


def test_repository_config_points_at_documents_tempjarvis():
    folders = load_config().reference_folders
    assert [f.path.parts[-2:] for f in folders] == [("Documents", "TempJarvis")]
    assert folders[0].classification is Classification.CONFIDENTIAL


def test_reference_files_are_searchable_in_place(brain, ref_dir):
    (ref_dir / "budget.md").write_text("Capex plan for Balikpapan data center: 30MW pilot.", encoding="utf-8")
    result = brain.search("balikpapan capex")
    assert len(result.hits) == 1
    hit = result.hits[0]
    assert hit.document.classification is Classification.CONFIDENTIAL
    assert hit.document.metadata["source"] == "budget.md"
    assert list(brain.config.vault_dir.glob("ref-*")) == []  # nothing copied into the vault


def test_secret_subfolder_raises_classification_and_is_withheld(brain, ref_dir):
    (ref_dir / "SECRET").mkdir()
    (ref_dir / "SECRET" / "merger.txt").write_text("merger target nusantara", encoding="utf-8")
    (ref_dir / "PUBLIC").mkdir()
    (ref_dir / "PUBLIC" / "note.txt").write_text("merger press note", encoding="utf-8")
    result = brain.search("merger")
    assert result.withheld_private_runtime == 1
    assert [h.document.classification for h in result.hits] == [Classification.CONFIDENTIAL]  # never lowered


def test_hidden_lock_and_symlinked_files_are_ignored(brain, ref_dir, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("leak candidate", encoding="utf-8")
    os.symlink(outside, ref_dir / "link.txt")
    (ref_dir / ".hidden.txt").write_text("leak candidate", encoding="utf-8")
    (ref_dir / "~$lock.docx").write_bytes(b"x")
    assert brain.list_documents() == []
    assert brain.search("leak candidate").hits == []


def test_edits_are_picked_up_without_restart(brain, ref_dir):
    path = ref_dir / "kpi.txt"
    path.write_text("churn target five percent", encoding="utf-8")
    assert brain.search("churn").hits
    path.write_text("retention target ninety percent", encoding="utf-8")
    os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000_000))
    assert not brain.search("churn").hits
    assert brain.search("retention").hits


def test_role_restricted_folder(tmp_path, ref_dir):
    raw = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    raw["reference_folders"] = [{"path": str(ref_dir), "classification": "INTERNAL", "allowed_roles": ["Board"]}]
    brain = PrivateBrain.open(parse_config(raw, tmp_path / "base"), key=Fernet.generate_key())
    (ref_dir / "minutes.txt").write_text("board dividend decision", encoding="utf-8")
    assert brain.search("dividend").hits == []  # local principal has role OWNER only
    board = AccessContext("sec", frozenset({"Board"}), Classification.CONFIDENTIAL)
    assert brain.search("dividend", context=board).hits


def test_office_and_pdf_extraction(tmp_path):
    docx = pytest.importorskip("docx")
    pptx = pytest.importorskip("pptx")
    pytest.importorskip("pypdf")
    Canvas = pytest.importorskip("reportlab.pdfgen.canvas").Canvas

    d = docx.Document()
    d.add_paragraph("Docx strategy paragraph")
    d.save(tmp_path / "a.docx")
    p = pptx.Presentation()
    slide = p.slides.add_slide(p.slide_layouts[5])
    slide.shapes.title.text = "Pptx roadmap title"
    p.save(tmp_path / "b.pptx")
    c = Canvas(str(tmp_path / "c.pdf"))
    c.drawString(72, 720, "Pdf revenue line")
    c.save()

    assert "Docx strategy paragraph" in extract_text(tmp_path / "a.docx")
    assert "Pptx roadmap title" in extract_text(tmp_path / "b.pptx")
    assert "Pdf revenue line" in extract_text(tmp_path / "c.pdf")


def test_unreadable_file_is_skipped_not_fatal(brain, ref_dir):
    (ref_dir / "broken.pdf").write_bytes(b"%PDF-1.4 not really")
    (ref_dir / "ok.txt").write_text("valuation memo", encoding="utf-8")
    result = brain.search("valuation memo")
    assert [h.document.metadata["source"] for h in result.hits] == ["ok.txt"]
    with pytest.raises(ExtractionError):
        extract_text(ref_dir / "broken.pdf")


def test_reference_files_cannot_be_deleted(brain, ref_dir, monkeypatch):
    (ref_dir / "keep.txt").write_text("keep this", encoding="utf-8")
    doc_id = brain.list_documents()[0].document_id
    with pytest.raises(ValueError):
        brain.delete(doc_id)
    monkeypatch.setattr(action, "_get_brain", lambda: brain)
    out = action.private_brain({"operation": "forget", "document_id": doc_id})
    assert "never deletes" in out and (ref_dir / "keep.txt").exists()
    assert "reference folder" in action.private_brain({"operation": "list"})

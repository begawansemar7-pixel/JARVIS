"""CEO document production: board reports (.docx/.pdf) and presentations (.pptx/.pdf).

Side-effect class A1 (AGENTS.md §9): writes NEW files only — existing files are
never overwritten — and the whole set can be removed again through core/undo.

Content comes from the model, either as explicit sections/slides or as the CEO
Decision Output Schema from skills/ceo-decision/SKILL.md. Files land in
~/Documents/JARVIS (override with JARVIS_DOCUMENTS_DIR).
"""
from __future__ import annotations

import json

from core.undo import push_undo
from documents import (
    ExecutiveDocument, decision_to_document, generate, output_dir, parse_classification,
    parse_sections, parse_slides,
)
from documents.model import text_list


def _build_document(params: dict) -> ExecutiveDocument:
    classification = parse_classification(params.get("classification"))
    title = str(params.get("title") or "").strip()
    subtitle = str(params.get("subtitle") or "").strip()
    author = str(params.get("author") or "").strip()

    decision = params.get("decision_json")
    if decision:
        if isinstance(decision, str):
            try:
                decision = json.loads(decision)
            except json.JSONDecodeError:
                raise ValueError("decision_json is not valid JSON") from None
        doc = decision_to_document(decision, title=title, subtitle=subtitle, author=author,
                                   classification=classification)
    else:
        if not title:
            raise ValueError("a title is required")
        doc = ExecutiveDocument(title=title, subtitle=subtitle, author=author,
                                classification=classification)

    # Explicit content always wins over what was derived from the decision.
    if params.get("summary"):
        doc.summary = text_list(params["summary"])
    if params.get("sections"):
        doc.sections = parse_sections(params["sections"])
    if params.get("slides"):
        doc.slides = parse_slides(params["slides"])
    return doc


def ceo_document(parameters: dict, player=None) -> str:
    params = parameters or {}
    document_type = str(params.get("document_type") or "report").strip().lower()
    try:
        doc = _build_document(params)
        files = generate(doc, document_type, params.get("formats"))
    except (ValueError, FileExistsError) as e:
        return f"Document not created: {e}"
    except OSError as e:
        return f"Document not created: could not write to {output_dir()} ({e.strerror or type(e).__name__})."
    except Exception as e:
        print(f"[CEODocument] generation failed: {type(e).__name__}: {e}")
        return f"Document not created: generation failed ({type(e).__name__})."

    def _undo(paths=tuple(f.path for f in files)):
        for p in paths:
            p.unlink(missing_ok=True)
        return f"Removed {len(paths)} generated document file(s)."

    push_undo(f"created {len(files)} CEO document file(s)", _undo)
    names = ", ".join(f.path.name for f in files)
    if player:
        try:
            player.write_log(f"SYS: CEO documents saved to {files[0].path.parent}: {names}")
        except Exception:
            pass
    return f"Saved {len(files)} file(s) to {files[0].path.parent}: {names}."


_TABLE_SCHEMA = {
    "type": "OBJECT",
    "description": "Optional table.",
    "properties": {
        "columns": {"type": "ARRAY", "items": {"type": "STRING"}},
        "rows": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "STRING"}}},
    },
}

TOOL = {
    "name": "ceo_document",
    "description": (
        "Creates CEO-level documents as real files: a board/executive REPORT (Word .docx and/or PDF) "
        "and/or a PRESENTATION deck (PowerPoint .pptx and/or PDF), saved in the user's "
        "Documents/JARVIS folder. Use when the user asks to make, write or export a report, laporan, "
        "memo, board paper, slide, deck or presentasi — including turning a CEO decision analysis "
        "into a board presentation. Either pass decision_json (the CEO Decision Output Schema: "
        "decision_question, options, recommendation, timing, triggers, execution_plan, data_gaps …), "
        "which yields a full report and the 12–18 slide board storyline, or pass title with "
        "summary/sections (report) and slides (presentation). Write the content in the user's "
        "language; every slide needs one clear executive message. Never invent figures: put "
        "[DATA GAP] where evidence is missing. A '.doc' request produces .docx. Only report success "
        "after this tool returns the saved file names. Do NOT use to edit existing files "
        "(use file_processor) or for spreadsheets."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "document_type": {"type": "STRING", "description": "report | presentation | both. Default report."},
            "formats": {"type": "STRING", "description": "Comma-separated: docx, pptx, pdf. Default report=docx,pdf; presentation=pptx,pdf."},
            "title": {"type": "STRING", "description": "Document title. Required unless decision_json has a decision_question."},
            "subtitle": {"type": "STRING", "description": "Optional subtitle."},
            "author": {"type": "STRING", "description": "Optional author or decision owner."},
            "classification": {"type": "STRING", "description": "Marking printed on every page: PUBLIC, INTERNAL, CONFIDENTIAL, SECRET or TOP_SECRET. Default INTERNAL."},
            "decision_json": {"type": "STRING", "description": "Optional CEO Decision Output Schema as a JSON string."},
            "summary": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Report: executive summary bullets."},
            "sections": {
                "type": "ARRAY",
                "description": "Report sections in order.",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "heading": {"type": "STRING"},
                        "paragraphs": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "bullets": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "table": _TABLE_SCHEMA,
                    },
                },
            },
            "slides": {
                "type": "ARRAY",
                "description": "Presentation slides in order (a title slide is added automatically).",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING", "description": "Short slide label."},
                        "message": {"type": "STRING", "description": "The one executive message (SO WHAT?)."},
                        "bullets": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "table": _TABLE_SCHEMA,
                        "notes": {"type": "STRING", "description": "Speaker notes."},
                    },
                },
            },
        },
        "required": ["document_type"],
    },
    "handler": ceo_document,
}

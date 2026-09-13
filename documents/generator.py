"""Write an ExecutiveDocument to disk in the requested formats.

Output goes to ~/Documents/JARVIS unless JARVIS_DOCUMENTS_DIR is set. Files are
never overwritten: a numeric suffix is added when a name is already taken.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .model import ExecutiveDocument

ENV_OUTPUT_DIR = "JARVIS_DOCUMENTS_DIR"
DOCUMENT_TYPES = ("report", "presentation", "both")
FORMATS = ("docx", "pptx", "pdf")
DEFAULT_FORMATS = {
    "report": ("docx", "pdf"),
    "presentation": ("pptx", "pdf"),
    "both": ("docx", "pptx", "pdf"),
}


@dataclass(frozen=True)
class GeneratedFile:
    kind: str      # "report" | "presentation"
    format: str    # "docx" | "pptx" | "pdf"
    path: Path


def output_dir() -> Path:
    override = os.environ.get(ENV_OUTPUT_DIR)
    return Path(override).expanduser() if override else Path.home() / "Documents" / "JARVIS"


def slugify(text: str, max_len: int = 60) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-")
    return (slug[:max_len].rstrip("-") or "Document")


def parse_formats(raw, document_type: str) -> tuple[str, ...]:
    if document_type not in DOCUMENT_TYPES:
        raise ValueError(f"document_type must be one of {', '.join(DOCUMENT_TYPES)}")
    if not raw:
        return DEFAULT_FORMATS[document_type]
    items = raw if isinstance(raw, (list, tuple)) else re.split(r"[,\s]+", str(raw))
    formats = []
    for item in items:
        fmt = str(item).strip().lower().lstrip(".")
        if not fmt:
            continue
        if fmt == "doc":
            fmt = "docx"   # Word document; the legacy binary .doc format is not produced
        if fmt not in FORMATS:
            raise ValueError(f"unsupported format {item!r}; use docx, pptx or pdf")
        if fmt not in formats:
            formats.append(fmt)
    if not formats:
        return DEFAULT_FORMATS[document_type]
    if document_type == "report" and formats == ["pptx"]:
        raise ValueError("a report is produced as docx or pdf; use document_type=presentation for pptx")
    if document_type == "presentation" and formats == ["docx"]:
        raise ValueError("a presentation is produced as pptx or pdf; use document_type=report for docx")
    return tuple(formats)


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{i}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"too many files named {path.name}")


def generate(document: ExecutiveDocument, document_type: str, formats=None,
             directory: Path | None = None, now: datetime | None = None) -> list[GeneratedFile]:
    from .docx_writer import write_docx
    from .pdf_writer import write_report_pdf, write_slides_pdf
    from .pptx_writer import write_pptx

    fmts = parse_formats(formats, document_type)
    kinds = ("report", "presentation") if document_type == "both" else (document_type,)
    if "report" in kinds and not (document.sections or document.summary):
        raise ValueError("a report needs at least one section or an executive summary")
    if "presentation" in kinds and not document.slides:
        raise ValueError("a presentation needs at least one slide")

    target = directory or output_dir()
    target.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M")
    base = slugify(document.title)

    plan = []
    for kind in kinds:
        label = "CEO-Report" if kind == "report" else "CEO-Deck"
        for fmt in fmts:
            if (kind, fmt) in (("report", "pptx"), ("presentation", "docx")):
                continue
            plan.append((kind, fmt, f"{stamp}_{label}_{base}.{fmt}"))

    writers = {
        ("report", "docx"): write_docx,
        ("report", "pdf"): write_report_pdf,
        ("presentation", "pptx"): write_pptx,
        ("presentation", "pdf"): write_slides_pdf,
    }
    created: list[GeneratedFile] = []
    try:
        for kind, fmt, name in plan:
            path = _unique(target / name)
            writers[(kind, fmt)](document, path)
            created.append(GeneratedFile(kind, fmt, path))
    except Exception:
        for item in created:            # no half-finished document sets
            item.path.unlink(missing_ok=True)
        raise
    return created


__all__ = ["DOCUMENT_TYPES", "ENV_OUTPUT_DIR", "FORMATS", "GeneratedFile", "generate", "output_dir",
           "parse_formats", "slugify"]

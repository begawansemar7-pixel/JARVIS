"""Executive document production (Word, PowerPoint, PDF) for JARVIS."""

from .generator import DOCUMENT_TYPES, FORMATS, GeneratedFile, generate, output_dir
from .model import (
    ExecutiveDocument, Section, Slide, Table, decision_to_document, parse_classification,
    parse_sections, parse_slides,
)

__all__ = [
    "DOCUMENT_TYPES", "FORMATS", "GeneratedFile", "generate", "output_dir",
    "ExecutiveDocument", "Section", "Slide", "Table", "decision_to_document",
    "parse_classification", "parse_sections", "parse_slides",
]

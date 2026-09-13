"""Shared visual identity for executive documents (all formats)."""
from __future__ import annotations

from pathlib import Path

NAVY = (0x0B, 0x1F, 0x3A)
GOLD = (0xC8, 0xA2, 0x4A)
INK = (0x1F, 0x29, 0x37)
MUTED = (0x6B, 0x72, 0x80)
RULE = (0xE5, 0xE7, 0xEB)
TABLE_STRIPE = (0xF3, 0xF4, 0xF6)
WHITE = (0xFF, 0xFF, 0xFF)

FONT = "Arial"  # present on macOS, Windows and Office for Mac

# TrueType fonts with broad Unicode coverage (Indonesian, CJK for the I Ching lens).
UNICODE_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/ARIALUNI.TTF",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
UNICODE_BOLD_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def hex_color(rgb: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % rgb


def first_existing(paths) -> Path | None:
    for p in paths:
        if Path(p).is_file():
            return Path(p)
    return None


def marking(classification: str) -> str:
    return classification.replace("_", " ")

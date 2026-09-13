"""PDF writers: an A4 report and a 16:9 slide deck, both via reportlab."""
from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Frame, KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table as RLTable,
    TableStyle,
)

from . import theme
from .model import ExecutiveDocument, Slide, Table, paginate_slides

SLIDE_SIZE = (960, 540)  # 13.333in x 7.5in at 72pt/in
_fonts: tuple[str, str] | None = None


def _register_fonts() -> tuple[str, str]:
    """Prefer a Unicode TrueType font so Indonesian and CJK text render correctly."""
    global _fonts
    if _fonts:
        return _fonts
    regular = theme.first_existing(theme.UNICODE_FONT_CANDIDATES)
    bold = theme.first_existing(theme.UNICODE_BOLD_CANDIDATES)
    if regular is None:
        _fonts = ("Helvetica", "Helvetica-Bold")
        return _fonts
    pdfmetrics.registerFont(TTFont("JarvisSans", str(regular)))
    bold_name = "JarvisSans"
    if bold is not None:
        pdfmetrics.registerFont(TTFont("JarvisSans-Bold", str(bold)))
        bold_name = "JarvisSans-Bold"
    _fonts = ("JarvisSans", bold_name)
    return _fonts


def _c(rgb) -> colors.Color:
    return colors.HexColor(theme.hex_color(rgb))


# CJK and other wide scripts: the bold face (Arial Bold) has no glyphs for them.
_WIDE_SCRIPT = re.compile(r"[⺀-鿿가-힯豈-﫿＀-￯]+")


def _p(text: str) -> str:
    """Escape for Paragraph markup; force wide-script runs onto the Unicode regular face."""
    regular, _bold = _register_fonts()
    markup = escape(text).replace("\n", "<br/>")
    if regular == "Helvetica":
        return markup
    return _WIDE_SCRIPT.sub(lambda m: f'<font name="{regular}">{m.group(0)}</font>', markup)


def _styles():
    regular, bold = _register_fonts()
    return {
        "title": ParagraphStyle("title", fontName=bold, fontSize=26, leading=32, textColor=_c(theme.NAVY)),
        "subtitle": ParagraphStyle("subtitle", fontName=regular, fontSize=14, leading=18, textColor=_c(theme.MUTED)),
        "h1": ParagraphStyle("h1", fontName=bold, fontSize=15, leading=19, textColor=_c(theme.NAVY),
                             spaceBefore=14, spaceAfter=6),
        "body": ParagraphStyle("body", fontName=regular, fontSize=10.5, leading=15, textColor=_c(theme.INK)),
        "cell": ParagraphStyle("cell", fontName=regular, fontSize=9, leading=12, textColor=_c(theme.INK)),
        "head": ParagraphStyle("head", fontName=bold, fontSize=9, leading=12, textColor=colors.white),
        "slide_cell": ParagraphStyle("slide_cell", fontName=regular, fontSize=15, leading=19,
                                     textColor=_c(theme.INK)),
        "slide_head": ParagraphStyle("slide_head", fontName=bold, fontSize=15, leading=19,
                                     textColor=colors.white),
        "slide_label": ParagraphStyle("slide_label", fontName=bold, fontSize=13, leading=16,
                                      textColor=_c(theme.GOLD)),
        "slide_msg": ParagraphStyle("slide_msg", fontName=bold, fontSize=26, leading=32, textColor=_c(theme.NAVY)),
        "slide_bullet": ParagraphStyle("slide_bullet", fontName=regular, fontSize=18, leading=24,
                                       textColor=_c(theme.INK), spaceAfter=8),
        "cover_title": ParagraphStyle("cover_title", fontName=bold, fontSize=38, leading=44, textColor=colors.white),
        "cover_sub": ParagraphStyle("cover_sub", fontName=regular, fontSize=20, leading=24, textColor=_c(theme.GOLD)),
        "bold": bold,
        "regular": regular,
    }


def _rl_table(table: Table, width: float, st, slide: bool = False) -> RLTable:
    head, cell, pad = (st["slide_head"], st["slide_cell"], 8) if slide else (st["head"], st["cell"], 4)
    data = [[Paragraph(_p(c), head) for c in table.columns]]
    data += [[Paragraph(_p(v), cell) for v in row] for row in table.rows]
    t = RLTable(data, colWidths=[width / len(table.columns)] * len(table.columns), repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), _c(theme.NAVY)),
        ("GRID", (0, 0), (-1, -1), 0.4, _c(theme.RULE)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
    ]
    style += [("BACKGROUND", (0, r), (-1, r), _c(theme.TABLE_STRIPE)) for r in range(2, len(data), 2)]
    t.setStyle(TableStyle(style))
    return t


def _bullet_list(items: list[str], style) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(_p(i), style), leftIndent=12) for i in items],
        bulletType="bullet", bulletColor=_c(theme.GOLD), leftIndent=14, bulletFontSize=9,
    )


def write_report_pdf(document: ExecutiveDocument, path: Path) -> Path:
    st = _styles()
    marking = theme.marking(document.classification)

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont(st["bold"], 8)
        canvas.setFillColor(_c(theme.GOLD))
        canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 1.2 * cm, marking)
        canvas.drawCentredString(A4[0] / 2, 1.2 * cm, marking)
        canvas.setFillColor(_c(theme.MUTED))
        canvas.setFont(st["regular"], 8)
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm, title=document.title,
                            author=document.author or "JARVIS", subject=marking)
    width = A4[0] - 4 * cm
    story = [Paragraph(_p(document.title), st["title"])]
    if document.subtitle:
        story += [Spacer(1, 4), Paragraph(_p(document.subtitle), st["subtitle"])]
    meta = " · ".join(x for x in (document.author, document.date, marking) if x)
    story += [Spacer(1, 6), Paragraph(_p(meta), st["subtitle"]), Spacer(1, 10)]
    if document.summary:
        story += [Paragraph("Executive Summary", st["h1"]), _bullet_list(document.summary, st["body"])]
    for sec in document.sections:
        block = [Paragraph(_p(sec.heading), st["h1"])]
        block += [Paragraph(_p(p), st["body"]) for p in sec.paragraphs]
        story.append(KeepTogether(block[:2]))
        story += block[2:]
        if sec.bullets:
            story.append(_bullet_list(sec.bullets, st["body"]))
        if sec.table:
            story += [Spacer(1, 6), _rl_table(sec.table, width, st)]
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return path


def write_slides_pdf(document: ExecutiveDocument, path: Path) -> Path:
    from reportlab.pdfgen.canvas import Canvas

    st = _styles()
    w, h = SLIDE_SIZE
    margin = 50
    marking = theme.marking(document.classification)
    canvas = Canvas(str(path), pagesize=SLIDE_SIZE)
    canvas.setTitle(document.title)
    canvas.setAuthor(document.author or "JARVIS")
    canvas.setSubject(marking)

    # Title slide
    canvas.setFillColor(_c(theme.NAVY))
    canvas.rect(0, 0, w, h, stroke=0, fill=1)
    canvas.setFillColor(_c(theme.GOLD))
    canvas.rect(margin, 280, 86, 4, stroke=0, fill=1)
    Frame(margin, 295, w - 2 * margin, 150, showBoundary=0).addFromList(
        [Paragraph(_p(document.title), st["cover_title"])], canvas)
    if document.subtitle:
        Frame(margin, 200, w - 2 * margin, 70, showBoundary=0).addFromList(
            [Paragraph(_p(document.subtitle), st["cover_sub"])], canvas)
    canvas.setFont(st["regular"], 14)
    canvas.setFillColor(colors.white)
    canvas.drawString(margin, 70, " · ".join(x for x in (document.author, document.date) if x))
    canvas.setFillColor(_c(theme.GOLD))
    canvas.setFont(st["bold"], 14)
    canvas.drawRightString(w - margin, 70, marking)
    canvas.showPage()

    for number, slide in enumerate(paginate_slides(document.slides), start=2):
        _slide_page(canvas, document, slide, number, st, marking)
    canvas.save()
    return path


def _slide_page(canvas, document: ExecutiveDocument, slide: Slide, number: int, st, marking: str) -> None:
    w, h = SLIDE_SIZE
    margin = 50
    canvas.setFillColor(_c(theme.NAVY))
    canvas.rect(0, 0, 13, h, stroke=0, fill=1)
    story = [Paragraph(_p(slide.title.upper()), st["slide_label"]), Spacer(1, 10)]
    if slide.message:
        story += [Paragraph(_p(slide.message), st["slide_msg"]), Spacer(1, 18)]
    if slide.table:
        story.append(_rl_table(slide.table, w - 2 * margin, st, slide=True))
    else:
        story += [Paragraph(f'<font color="{theme.hex_color(theme.GOLD)}">■</font>&nbsp;&nbsp;{_p(b)}',
                            st["slide_bullet"]) for b in slide.bullets]
    Frame(margin, 60, w - 2 * margin, h - 90, showBoundary=0, leftPadding=0, rightPadding=0).addFromList(
        story, canvas)

    canvas.setStrokeColor(_c(theme.RULE))
    canvas.line(margin, 45, w - margin, 45)
    canvas.setFont(st["regular"], 10)
    canvas.setFillColor(_c(theme.MUTED))
    canvas.drawString(margin, 28, document.title[:80])
    canvas.drawRightString(w - margin, 28, str(number))
    canvas.setFont(st["bold"], 10)
    canvas.setFillColor(_c(theme.GOLD))
    canvas.drawCentredString(w / 2, 28, marking)
    canvas.showPage()


__all__ = ["write_report_pdf", "write_slides_pdf"]

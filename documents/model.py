"""Content model for executive documents, independent of the output format.

A report is a list of sections; a presentation is a list of slides. Both can be
supplied directly by the model or derived from the CEO Decision Output Schema
defined in skills/ceo-decision/SKILL.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

CLASSIFICATIONS = ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "SECRET", "TOP_SECRET")
DATA_GAP = "[DATA GAP]"
MAX_BULLETS_PER_SLIDE = 6
MAX_TABLE_ROWS_PER_SLIDE = 8


@dataclass
class Table:
    columns: list[str]
    rows: list[list[str]]


@dataclass
class Section:
    heading: str
    paragraphs: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    table: Table | None = None


@dataclass
class Slide:
    title: str
    message: str = ""
    bullets: list[str] = field(default_factory=list)
    table: Table | None = None
    notes: str = ""


@dataclass
class ExecutiveDocument:
    title: str
    subtitle: str = ""
    author: str = ""
    date: str = field(default_factory=lambda: date.today().isoformat())
    classification: str = "INTERNAL"
    summary: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    slides: list[Slide] = field(default_factory=list)


# -- parsing helpers ----------------------------------------------------------

def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def text_list(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [line.strip(" -•\t") for line in value.splitlines() if line.strip(" -•\t")]
    if isinstance(value, dict):
        return [f"{k}: {_text(v)}" for k, v in value.items() if _text(v)]
    return [_text(v) for v in value if _text(v)]


def _maybe_json(value):
    if isinstance(value, str) and value.strip()[:1] in ("[", "{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            raise ValueError("content is not valid JSON") from None
    return value


def parse_classification(label: str | None) -> str:
    value = (label or "INTERNAL").strip().upper().replace("-", "_").replace(" ", "_")
    if value not in CLASSIFICATIONS:
        raise ValueError(f"unknown classification {label!r}; use one of {', '.join(CLASSIFICATIONS)}")
    return value


def parse_table(raw) -> Table | None:
    raw = _maybe_json(raw)
    if not isinstance(raw, dict):
        return None
    columns = text_list(raw.get("columns"))
    rows = [[_text(c) for c in row] for row in raw.get("rows") or [] if isinstance(row, (list, tuple))]
    if not columns or not rows:
        return None
    width = len(columns)
    rows = [(row + [""] * width)[:width] for row in rows]
    return Table(columns, rows)


def parse_sections(raw) -> list[Section]:
    raw = _maybe_json(raw) or []
    if not isinstance(raw, list):
        raise ValueError("sections must be a list")
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        heading = _text(item.get("heading") or item.get("title"))
        if not heading:
            continue
        out.append(Section(
            heading=heading,
            paragraphs=text_list(item.get("paragraphs") or item.get("body")),
            bullets=text_list(item.get("bullets")),
            table=parse_table(item.get("table")),
        ))
    return out


def parse_slides(raw) -> list[Slide]:
    raw = _maybe_json(raw) or []
    if not isinstance(raw, list):
        raise ValueError("slides must be a list")
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = _text(item.get("title"))
        if not title:
            continue
        out.append(Slide(
            title=title,
            message=_text(item.get("message")),
            bullets=text_list(item.get("bullets")),
            table=parse_table(item.get("table")),
            notes=_text(item.get("notes")),
        ))
    return out


def paginate_slides(slides: list[Slide]) -> list[Slide]:
    """Split overfull slides into continuation slides so nothing overflows."""
    out = []
    for slide in slides:
        bullets = slide.bullets
        rows = slide.table.rows if slide.table else []
        chunks = max(
            1,
            -(-len(bullets) // MAX_BULLETS_PER_SLIDE),
            -(-len(rows) // MAX_TABLE_ROWS_PER_SLIDE),
        )
        for i in range(chunks):
            part_bullets = bullets[i * MAX_BULLETS_PER_SLIDE:(i + 1) * MAX_BULLETS_PER_SLIDE]
            part_rows = rows[i * MAX_TABLE_ROWS_PER_SLIDE:(i + 1) * MAX_TABLE_ROWS_PER_SLIDE]
            out.append(Slide(
                title=slide.title if i == 0 else f"{slide.title} (cont.)",
                message=slide.message if i == 0 else "",
                bullets=part_bullets,
                table=Table(slide.table.columns, part_rows) if slide.table and part_rows else None,
                notes=slide.notes if i == 0 else "",
            ))
    return out


# -- CEO Decision Output Schema -> document -----------------------------------

def _or_gap(value) -> str:
    return _text(value) or DATA_GAP


def _items_or_gap(value) -> list[str]:
    return text_list(value) or [DATA_GAP]


def _option_rows(options) -> tuple[list[str], list[str], Table | None]:
    """Return (option bullets, consequence bullets, score table)."""
    bullets, consequences, rows, criteria = [], [], [], []
    for opt in options or []:
        if not isinstance(opt, dict):
            bullets.append(_text(opt))
            continue
        name = _text(opt.get("name") or opt.get("title") or opt.get("option")) or "Option"
        desc = _text(opt.get("description") or opt.get("summary"))
        bullets.append(f"{name}: {desc}" if desc else name)
        for key in ("second_order", "second_order_effects", "consequences"):
            for c in text_list(opt.get(key)):
                consequences.append(f"{name} — {c}")
        scores = opt.get("scores")
        if isinstance(scores, dict) and scores:
            criteria = criteria or list(scores.keys())
            rows.append([name] + [_text(scores.get(c)) for c in criteria])
    table = Table(["Option"] + [c.replace("_", " ").title() for c in criteria], rows) if rows else None
    return bullets, consequences, table


def _named_items(items) -> list[str]:
    out = []
    for item in items or []:
        if isinstance(item, dict):
            label = _text(item.get("name") or item.get("trigger") or item.get("tension") or item.get("stakeholder"))
            rest = "; ".join(f"{k}: {_text(v)}" for k, v in item.items()
                             if k not in ("name", "trigger", "tension", "stakeholder") and _text(v))
            out.append(f"{label} — {rest}" if label and rest else label or rest)
        elif _text(item):
            out.append(_text(item))
    return out


def decision_to_document(decision: dict, *, title: str = "", subtitle: str = "",
                         author: str = "", classification: str = "INTERNAL") -> ExecutiveDocument:
    """Map the CEO Decision Output Schema to a report and a board storyline.

    Missing material fields are rendered as [DATA GAP], never invented."""
    if not isinstance(decision, dict):
        raise ValueError("decision must be a JSON object following the CEO Decision Output Schema")
    rec = decision.get("recommendation") or {}
    timing = decision.get("timing") or {}
    phase = decision.get("strategic_phase") or {}
    plan = decision.get("execution_plan") or {}
    question = _or_gap(decision.get("decision_question"))
    option_bullets, consequences, score_table = _option_rows(decision.get("options"))
    tensions = _named_items(decision.get("yin_yang_tensions"))
    triggers = _named_items(decision.get("triggers"))
    stakeholders = _named_items(decision.get("stakeholders"))
    roadmap = [f"{k.replace('_', ' ').title()}: {'; '.join(text_list(v))}" for k, v in plan.items()
               if text_list(v)] if isinstance(plan, dict) else text_list(plan)
    risks = text_list(rec.get("risks"))
    mitigations = text_list(rec.get("mitigations"))
    gaps = text_list(decision.get("data_gaps"))
    confidence = _text(decision.get("confidence"))

    summary = [
        f"Decision: {_or_gap(rec.get('decision'))}",
        f"Why: {_or_gap(rec.get('why'))}",
        f"Timing: {_or_gap(timing.get('classification'))} — {_or_gap(timing.get('rationale'))}",
    ]
    if confidence:
        summary.append(f"Confidence: {confidence}")

    frame = [
        f"Decision question: {question}",
        f"Decision owner: {_or_gap(decision.get('decision_owner'))}",
        f"Deadline: {_or_gap(decision.get('deadline'))}",
        f"Objective: {_or_gap(decision.get('objective'))}",
    ]
    sections = [
        Section("Decision Frame", bullets=frame),
        Section("Current State", bullets=_items_or_gap(decision.get("current_state"))),
        Section("Change Vector", bullets=_items_or_gap(decision.get("change_vector"))),
        Section("Strategic Phase (I Ching-inspired lens, not a prediction)", bullets=[
            f"Pattern: {_or_gap(phase.get('pattern'))}",
            f"Rationale: {_or_gap(phase.get('rationale'))}",
        ]),
        Section("Yin-Yang Tensions", bullets=tensions or [DATA_GAP]),
        Section("Timing", bullets=[
            f"Classification: {_or_gap(timing.get('classification'))}",
            f"Rationale: {_or_gap(timing.get('rationale'))}",
        ]),
        Section("Stakeholders and Governance", bullets=stakeholders or [DATA_GAP]),
        Section("Strategic Options", bullets=option_bullets or [DATA_GAP], table=score_table),
        Section("Second-Order Consequences", bullets=consequences or [DATA_GAP]),
        Section("Risks and Mitigations", bullets=[f"Risk: {r}" for r in risks]
                + [f"Mitigation: {m}" for m in mitigations] or [DATA_GAP]),
        Section("CEO Recommendation", bullets=[
            f"Decision: {_or_gap(rec.get('decision'))}",
            f"Why: {_or_gap(rec.get('why'))}",
            f"Why now: {_or_gap(rec.get('why_now'))}",
        ] + [f"Must be true: {x}" for x in text_list(rec.get("what_must_be_true"))]
          + [f"Do not: {x}" for x in text_list(rec.get("what_not_to_do"))]),
        Section("Execution Roadmap (30/90/180)", bullets=roadmap or [DATA_GAP]),
        Section("Decision Triggers and Early Warning", bullets=triggers or [DATA_GAP]),
        Section("Data Gaps", bullets=gaps or ["No material data gaps declared."]),
    ]

    slides = [
        Slide("Executive message", _or_gap(rec.get("decision")), summary[1:]),
        Slide("Decision to be made", question, frame[1:]),
        Slide("Why now", _or_gap(rec.get("why_now")), [f"Timing: {_or_gap(timing.get('classification'))}"]),
        Slide("What is changing", "", _items_or_gap(decision.get("change_vector"))),
        Slide("Strategic diagnosis", "", _items_or_gap(decision.get("current_state"))),
        Slide("Strategic phase", _or_gap(phase.get("pattern")), [_or_gap(phase.get("rationale"))],
              notes="I Ching is used as a reasoning metaphor only, never as a prediction."),
        Slide("Yin-Yang tension", "", tensions or [DATA_GAP]),
        Slide("Strategic options", "", option_bullets or [DATA_GAP]),
    ]
    if score_table:
        slides.append(Slide("Option comparison", "Scores 1–10 per dimension; trade-offs stay visible.",
                            table=score_table))
    slides += [
        Slide("Second-order consequences", "", consequences or [DATA_GAP]),
        Slide("Risk and pre-mortem", "", [f"Risk: {r}" for r in risks]
              + [f"Mitigation: {m}" for m in mitigations] or [DATA_GAP]),
        Slide("Governance and trust", "", stakeholders or [DATA_GAP]),
        Slide("Recommendation", _or_gap(rec.get("decision")),
              [f"Must be true: {x}" for x in text_list(rec.get("what_must_be_true"))]
              + [f"Do not: {x}" for x in text_list(rec.get("what_not_to_do"))] or [DATA_GAP]),
        Slide("30/90/180 execution roadmap", "", roadmap or [DATA_GAP]),
        Slide("Early-warning triggers", "", triggers or [DATA_GAP]),
        Slide("Final CEO decision", _or_gap(rec.get("decision")),
              [f"Data gaps: {len(gaps)}"] + ([f"Confidence: {confidence}"] if confidence else [])),
    ]

    return ExecutiveDocument(
        title=title or _text(decision.get("decision_question")) or "CEO Decision",
        subtitle=subtitle or "CEO Decision Intelligence",
        author=author or _text(decision.get("decision_owner")),
        classification=parse_classification(classification),
        summary=summary,
        sections=sections,
        slides=slides,
    )

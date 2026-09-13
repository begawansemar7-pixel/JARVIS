"""Consulting-grade strategy research: evidence gathering and market sizing.

Side-effect class A1 (AGENTS.md §9): sends search queries to public search
engines, fetches public web pages, and writes a new dossier folder under
~/Documents/JARVIS/Research that core/undo can remove again.

The reasoning procedure lives in skills/strategy-research/SKILL.md; this action
does the parts that must be deterministic — fetching, citing, triangulating and
arithmetic.
"""
from __future__ import annotations

import json
import shutil

from core.undo import push_undo
from research.dossier import (
    model_view, new_dossier_dir, render_sizing_markdown, research_root, write_evidence,
)
from research.evidence import MAX_QUESTIONS, gather_evidence
from research.sizing import human, parse_drivers, size_market

# Markers that only appear in Private Brain output: such text must never become a web query.
_CONFIDENTIAL_MARKERS = ("[PRIVATE_BRAIN]",)


def _list(value) -> list:
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("["):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("list parameter is not valid JSON") from None
        else:
            return [line.strip(" -•\t") for line in value.splitlines() if line.strip(" -•\t")]
    return list(value or [])


def _register_undo(directory, label: str) -> None:
    root = research_root().resolve()

    def _undo(path=directory):
        resolved = path.resolve()
        if root in resolved.parents and resolved.exists():
            shutil.rmtree(resolved)
            return "Removed the research dossier."
        return "The research dossier was already gone."

    push_undo(label, _undo)


def _gather(params: dict, player) -> str:
    key_question = str(params.get("key_question") or "").strip()
    questions = [str(q) for q in _list(params.get("questions"))]
    context = str(params.get("context") or "").strip()
    if not key_question:
        return "Research not started: key_question is required."
    if not questions:
        return "Research not started: provide the issue-tree questions to research."
    outbound = " ".join([key_question, context, *questions])
    if any(marker in outbound for marker in _CONFIDENTIAL_MARKERS):
        return ("Research not started: the queries contain Private Brain content. Rephrase them with "
                "public terms only; confidential material never goes to web search.")
    if len(questions) > MAX_QUESTIONS:
        questions = questions[:MAX_QUESTIONS]

    if player:
        try:
            player.write_log(f"SYS: Researching {len(questions)} question(s): {key_question[:80]}")
        except Exception:
            pass
    pack = gather_evidence(key_question, questions, context=context,
                           include_news=str(params.get("include_news", "true")).lower() != "false")
    directory = new_dossier_dir(key_question)
    write_evidence(pack, directory)
    _register_undo(directory, "created a research dossier")
    return model_view(pack, directory)


def _size(params: dict) -> str:
    title = str(params.get("title") or params.get("key_question") or "Market").strip()
    unit = str(params.get("unit") or "").strip()
    result = size_market(parse_drivers(_list(params.get("drivers"))))
    directory = new_dossier_dir(f"sizing {title}")
    (directory / "sizing.md").write_text(render_sizing_markdown(title, result, unit), encoding="utf-8")
    _register_undo(directory, "created a market sizing file")

    u = f" {unit}" if unit else ""
    top = result.sensitivity[0]
    missing = [d.name for d in result.drivers if not d.source]
    lines = [
        f"[MARKET_SIZING] {title}: low {human(result.low)}{u}, base {human(result.base)}{u}, "
        f"high {human(result.high)}{u}.",
        f"Most sensitive driver: {top[0]} (swing {human(top[3])}{u}).",
        "Sensitivity order: " + ", ".join(row[0] for row in result.sensitivity) + ".",
        f"Workings saved to {directory / 'sizing.md'}.",
    ]
    if missing:
        lines.append("Drivers without a source (mark as assumptions): " + ", ".join(missing) + ".")
    return "\n".join(lines)


def strategy_research(parameters: dict, player=None) -> str:
    params = parameters or {}
    operation = str(params.get("operation") or "gather_evidence").strip().lower()
    try:
        if operation == "gather_evidence":
            return _gather(params, player)
        if operation == "size_market":
            return _size(params)
        return f"Unknown operation '{operation}'. Use gather_evidence or size_market."
    except ValueError as e:
        return f"Research not completed: {e}"
    except OSError as e:
        return f"Research not completed: could not write the dossier ({e.strerror or type(e).__name__})."
    except Exception as e:
        print(f"[StrategyResearch] {operation} failed: {type(e).__name__}: {e}")
        return f"Research not completed: {operation} failed ({type(e).__name__})."


TOOL = {
    "name": "strategy_research",
    "description": (
        "Consulting-grade strategy research (hypothesis-driven, evidence-based, cited) for market, "
        "industry, competitor, regulatory, technology and investment questions — 'riset pasar', "
        "'analisis industri', 'market sizing', 'due diligence', 'benchmark kompetitor'. "
        "operation=gather_evidence: pass the key_question and the MECE issue-tree questions (max 10); "
        "the tool searches public sources, scores credibility (T1 official … T5 user-generated), "
        "extracts quotable excerpts with [S#] citations, flags [DATA GAP] / [TRIANGULATION GAP], and "
        "saves a dossier in Documents/JARVIS/Research. operation=size_market: pass drivers "
        "(name, low, base, high, unit, source) that multiply to the market size; returns low/base/high "
        "and a sensitivity ranking — never do this arithmetic yourself. Queries go to public search "
        "engines: never include confidential or Private Brain content in them. Use web_search for a "
        "quick single fact and news_briefing for today's news instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "operation": {"type": "STRING", "description": "gather_evidence | size_market. Default gather_evidence."},
            "key_question": {"type": "STRING", "description": "The governing question the research must answer."},
            "questions": {"type": "ARRAY", "items": {"type": "STRING"},
                          "description": "gather_evidence: issue-tree leaf questions, each answerable with evidence."},
            "context": {"type": "STRING", "description": "gather_evidence: public scoping terms added to every query, e.g. 'Indonesia 2025'."},
            "include_news": {"type": "BOOLEAN", "description": "gather_evidence: also search recent news. Default true."},
            "title": {"type": "STRING", "description": "size_market: what is being sized."},
            "unit": {"type": "STRING", "description": "size_market: unit of the result, e.g. 'IDR/year' or 'USD'."},
            "drivers": {
                "type": "ARRAY",
                "description": "size_market: factors multiplied together (e.g. households × penetration × ARPU × 12).",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING"},
                        "low": {"type": "NUMBER"},
                        "base": {"type": "NUMBER"},
                        "high": {"type": "NUMBER"},
                        "unit": {"type": "STRING"},
                        "source": {"type": "STRING", "description": "[S#] reference or 'assumption'."},
                    },
                },
            },
        },
        "required": ["operation"],
    },
    "handler": strategy_research,
}

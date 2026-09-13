import json

import pytest

from actions import strategy_research as action
from core import undo
from core.action_loader import _validate
from research import evidence
from research.dossier import ENV_OUTPUT_DIR, render_evidence_markdown
from research.evidence import extract_excerpts, gather_evidence, html_to_text, is_public_http_url
from research.sizing import parse_drivers, size_market
from research.sources import credibility

PAGES = {
    "https://www.bps.go.id/dc": "<html><nav>menu</nav><p>Indonesia data center capacity reached 1,200 MW in 2024 "
                                "according to official statistics on data center capacity.</p><script>x()</script></html>",
    "https://www.reuters.com/dc": "<p>Analysts said Indonesia data center capacity could double by 2028, "
                                  "with investment of US$ 3 billion.</p>",
    "https://someblog.example.com/dc": "<p>I think data center capacity Indonesia is big lol.</p>",
}


@pytest.fixture
def offline(monkeypatch, tmp_path):
    def web(query, n):
        return [{"title": "BPS", "url": "https://www.bps.go.id/dc", "snippet": "official"},
                {"title": "Blog", "url": "https://someblog.example.com/dc", "snippet": "blog"}]

    def news(query, n):
        return [{"title": "Reuters", "url": "https://www.reuters.com/dc#top", "published": "2026-09-01"},
                {"title": "BPS dup", "url": "https://www.bps.go.id/dc"}]

    def fetch(url):
        if url not in PAGES:
            raise ValueError("offline")
        return PAGES[url]

    monkeypatch.setattr(evidence, "search_web", web)
    monkeypatch.setattr(evidence, "search_news", news)
    monkeypatch.setattr(evidence, "fetch_page", fetch)
    monkeypatch.setenv(ENV_OUTPUT_DIR, str(tmp_path))
    return tmp_path


def test_credibility_tiers_prefer_specific_patterns():
    assert credibility("https://www.bps.go.id/x").tier == "T1"
    assert credibility("https://brin.go.id/x").tier == "T2"      # longer pattern beats ".go.id"
    assert credibility("https://www.reuters.com/x").tier == "T3"
    assert credibility("https://example.org/x").tier == "T4"
    assert credibility("https://user.medium.com/x").tier == "T5"
    assert credibility("https://notreuters.com/x").tier == "T4"  # no suffix spoofing


def test_private_and_non_http_urls_are_refused():
    assert not is_public_http_url("http://127.0.0.1/admin")
    assert not is_public_http_url("http://192.168.1.1/")
    assert not is_public_http_url("http://169.254.169.254/latest/meta-data")
    assert not is_public_http_url("file:///etc/passwd")
    assert not is_public_http_url("ftp://example.com/")


def test_html_is_stripped_and_quantitative_sentences_preferred():
    text = html_to_text(PAGES["https://www.bps.go.id/dc"])
    assert "menu" not in text and "x()" not in text
    excerpts = extract_excerpts(
        "Data center capacity is a topic of interest in many countries around the world. "
        "Indonesia data center capacity reached 1,200 MW in 2024 per official statistics.",
        "Indonesia data center capacity",
    )
    assert excerpts[0].startswith("Indonesia data center capacity reached 1,200 MW")
    headings = "Indonesia Data Center Market Share & Size 2031 Outlook\nIndonesia Data Center Capacity Report"
    assert extract_excerpts(headings, "Indonesia data center capacity") == []


def test_gather_dedupes_ranks_cites_and_triangulates(offline):
    pack = gather_evidence("How big is Indonesia's data center market?",
                           ["Indonesia data center capacity", "   "], context="2024")
    assert len(pack.questions) == 1
    qe = pack.questions[0]
    urls = [s.url for s in qe.sources]
    assert len(urls) == len(set(urls)) == 3
    assert qe.sources[0].credibility.tier == "T1"
    assert qe.triangulated and qe.independent_domains == 3
    assert [s.ref for s in qe.sources] == ["S1", "S2", "S3"]
    assert any("1,200 MW" in e for s in qe.sources for e in s.excerpts)


def test_single_weak_source_is_flagged(monkeypatch, offline):
    monkeypatch.setattr(evidence, "search_web",
                        lambda q, n: [{"title": "Blog", "url": "https://someblog.example.com/dc"}])
    monkeypatch.setattr(evidence, "search_news", lambda q, n: [])
    qe = gather_evidence("k", ["Indonesia data center capacity"]).questions[0]
    assert not qe.triangulated and "TRIANGULATION GAP" in qe.note


def test_failing_backends_become_data_gaps(monkeypatch, offline):
    def boom(q, n):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(evidence, "search_web", boom)
    monkeypatch.setattr(evidence, "search_news", boom)
    qe = gather_evidence("k", ["anything at all"]).questions[0]
    assert qe.sources == [] and "DATA GAP" in qe.note


def test_market_sizing_scenarios_and_sensitivity():
    drivers = parse_drivers([
        {"name": "Firms", "low": 1000, "base": 2000, "high": 3000},
        {"name": "Adoption", "low": 0.1, "base": 0.2, "high": 0.25, "source": "[S2]"},
        {"name": "ARPU", "base": "1,000,000"},
    ])
    result = size_market(drivers)
    assert result.base == pytest.approx(2000 * 0.2 * 1_000_000)
    assert result.low == pytest.approx(1000 * 0.1 * 1_000_000)
    assert result.high == pytest.approx(3000 * 0.25 * 1_000_000)
    assert result.sensitivity[0][0] == "Firms"      # widest swing first
    assert result.sensitivity[-1][0] == "ARPU"      # no range, no swing


@pytest.mark.parametrize("bad", [
    [], [{"name": ""}], [{"name": "x", "base": "abc"}], [{"name": "x", "low": 5, "base": 1, "high": 9}],
    [{"name": "x", "base": -1}], [{"name": "x", "base": float("inf")}],
])
def test_invalid_drivers_are_rejected(bad):
    with pytest.raises(ValueError):
        parse_drivers(bad)


def test_action_contract_is_valid():
    assert _validate(action, "strategy_research.py").valid


def test_action_gather_writes_dossier_and_undo_removes_it(offline):
    undo.clear()
    out = action.strategy_research({
        "operation": "gather_evidence",
        "key_question": "How big is Indonesia's data center market?",
        "questions": ["Indonesia data center capacity"],
    })
    assert out.startswith("[RESEARCH_EVIDENCE]") and "[S1]" in out
    dossiers = list((offline / "Research").iterdir())
    assert len(dossiers) == 1
    data = json.loads((dossiers[0] / "evidence.json").read_text())
    assert data["questions"][0]["triangulated"] is True
    assert "## Sources" in (dossiers[0] / "evidence.md").read_text()
    undo.undo_last()
    assert list((offline / "Research").iterdir()) == []


def test_action_refuses_private_brain_content_in_queries(offline):
    out = action.strategy_research({
        "operation": "gather_evidence", "key_question": "k",
        "questions": ["[PRIVATE_BRAIN] Authorized private knowledge follows: merger target"],
    })
    assert "never goes to web search" in out
    assert not (offline / "Research").exists()


def test_action_size_market(offline):
    out = action.strategy_research({
        "operation": "size_market", "title": "SME cloud", "unit": "IDR/year",
        "drivers": [{"name": "SMEs", "low": 1e5, "base": 2e5, "high": 3e5, "source": "[S1]"},
                    {"name": "Spend", "low": 1e6, "base": 2e6, "high": 2e6}],
    })
    assert "base 400.00B IDR/year" in out and "Most sensitive driver: SMEs" in out
    assert "without a source" in out and "Spend" in out


def test_action_reports_bad_input(offline):
    assert action.strategy_research({"operation": "gather_evidence", "key_question": "k"}) \
        .startswith("Research not started")
    assert action.strategy_research({"operation": "size_market", "drivers": []}) \
        .startswith("Research not completed")
    assert "Unknown operation" in action.strategy_research({"operation": "dance"})


def test_markdown_log_lists_every_source_once(offline):
    pack = gather_evidence("k", ["Indonesia data center capacity", "Indonesia data center capacity 2028"])
    md = render_evidence_markdown(pack)
    assert md.count("[S1] ") == 1 and "## Q2." in md


def test_syndicated_research_is_labelled_but_not_strong():
    c = credibility("https://www.mordorintelligence.com/industry-reports/x")
    assert c.tier == "T4" and "Syndicated" in c.label and c.weight < 0.75

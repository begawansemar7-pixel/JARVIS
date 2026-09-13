from actions import news_briefing as nb


def test_normalize_domain_and_fingerprint():
    assert nb._domain("https://www.example.com/story?id=1") == "example.com"
    a = {"url": "https://example.com/a#x", "title": "Same story"}
    b = {"url": "https://example.com/a#y", "title": "Different text"}
    assert nb._fingerprint(a) == nb._fingerprint(b)


def test_deduplicate_keeps_highest_score():
    items = [
        {"url": "https://a.com/story", "title": "A", "score": 40},
        {"url": "https://a.com/story", "title": "A", "score": 90},
        {"url": "https://b.com/other", "title": "B", "score": 50},
    ]
    out = nb.deduplicate(items)
    assert len(out) == 2
    assert max(x["score"] for x in out) == 90


def test_deduplicate_collapses_same_title_with_different_urls():
    items = [
        {"url": "https://a.com/story", "title": "Same headline", "score": 80},
        {"url": "https://b.com/story-copy", "title": "Same headline", "score": 70},
    ]
    out = nb.deduplicate(items)
    assert len(out) == 1
    assert out[0]["score"] == 80


def test_cluster_events_groups_similar_headlines():
    items = [
        {"title": "Telkom spin off fiber business to unlock value", "score": 90, "source": "A"},
        {"title": "Telkom fiber spin-off aims to unlock value", "score": 80, "source": "B"},
        {"title": "Indonesia football final announced", "score": 70, "source": "C"},
    ]
    clusters = nb.cluster_events(items)
    assert len(clusters) == 2
    assert max(len(c["items"]) for c in clusters) == 2
    assert max(c["confirmation"] for c in clusters) > 0.5


def test_score_prefers_authoritative_source():
    registry = {"sources": {"telecom_telkom": [{"name": "Telkom", "domain": "telkom.co.id", "weight": 1.0}]}}
    taxonomy = {"categories": {"telecom_telkom": {"keywords": ["Telkom", "fiber"]}}}
    official = {"url": "https://telkom.co.id/news", "title": "Telkom fiber", "snippet": "fiber", "confirmation": 0.8}
    unknown = {"url": "https://unknown.example/news", "title": "Telkom fiber", "snippet": "fiber", "confirmation": 0.8}
    assert nb._score(official, "telecom_telkom", taxonomy, registry) > nb._score(unknown, "telecom_telkom", taxonomy, registry)


def test_render_contains_required_sections():
    text = nb.render_briefing({"id_trending": [], "ai_global": [], "ai_indonesia": [], "telecom_telkom": []})
    assert "Trending Indonesia" in text
    assert "AI Global" in text
    assert "AI Indonesia" in text
    assert "Telekomunikasi & Telkom" in text
    assert "What matters" in text
    assert "Watch next" in text


def test_collect_news_covers_all_categories(monkeypatch):
    calls = []

    def fake_fetch(category, taxonomy, max_results):
        calls.append(category)
        return []

    def fake_load(path):
        if str(path).endswith("news_sources.json"):
            return {"sources": {}}
        return {"categories": {c: {"keywords": [], "queries": []} for c in nb.CATEGORY_ORDER}}

    monkeypatch.setattr(nb, "_fetch_category", fake_fetch)
    monkeypatch.setattr(nb, "_load_json", fake_load)
    result = nb.collect_news(max_per_category=1)

    assert calls == list(nb.CATEGORY_ORDER)
    assert set(result) == set(nb.CATEGORY_ORDER)


def test_news_briefing_handles_invalid_max_items(monkeypatch):
    monkeypatch.setattr(nb, "collect_news", lambda max_per_category: {c: [] for c in nb.CATEGORY_ORDER})
    text = nb.news_briefing({"max_items": "not-a-number"})
    assert "NEWS INTELLIGENCE BRIEFING" in text

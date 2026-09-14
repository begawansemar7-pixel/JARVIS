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


def test_render_contains_three_topics_and_quote():
    quote = {"price": 2690.0, "currency": "IDR", "previous_close": 2650.0, "change": 40.0, "change_pct": 1.509,
             "day_high": 2700, "day_low": 2640, "volume": 81234500,
             "as_of": nb.datetime(2026, 9, 14, 15, 50, tzinfo=nb.WIB)}
    text = nb.render_briefing({c: [] for c in nb.CATEGORY_ORDER}, quote)
    assert "SAHAM TELKOM (TLKM)" in text
    assert "BERITA TELKOM INDONESIA" in text
    assert "TRENDING TOPIK AI" in text
    assert "TLKM IDR 2.690" in text and "▲ +40 (+1.51%)" in text
    assert "14 Sep 2026 15:50 WIB" in text and "Bukan rekomendasi investasi" in text
    assert "WHAT MATTERS" in text
    assert "**" not in text and "###" not in text


def test_render_without_quote_never_guesses_a_price():
    text = nb.render_briefing({c: [] for c in nb.CATEGORY_ORDER}, None)
    assert "Harga saham tidak dapat diambil" in text
    assert "IDR" not in text


def test_collect_news_covers_all_categories_in_parallel(monkeypatch):
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

    assert sorted(calls) == sorted(nb.CATEGORY_ORDER)
    assert list(result) == list(nb.CATEGORY_ORDER)


def test_rss_dates_are_parsed_for_recency():
    fresh = nb.datetime.now(nb.timezone.utc) - nb.timedelta(hours=2)
    rss_item = {"published": fresh.strftime("%a, %d %b %Y %H:%M:%S GMT")}
    assert 1.5 < nb._age_hours(rss_item) < 2.5
    assert nb._recency_score(rss_item) > 0.9
    assert nb._recency_score({"published": "not a date"}) == 0.65


def test_stale_undated_and_off_topic_stories_are_dropped(monkeypatch):
    now = nb.datetime.now(nb.timezone.utc)
    rows = [
        {"title": "Telkom expands data center - Kontan", "source": "Kontan", "url": "https://a.com/1",
         "published": (now - nb.timedelta(hours=3)).strftime("%a, %d %b %Y %H:%M:%S GMT")},
        {"title": "Old Telkom news", "url": "https://a.com/2", "published": (now - nb.timedelta(days=30)).isoformat()},
        {"title": "Undated Telkom tag page", "url": "https://a.com/tag/telkom"},
        {"title": "IHSG closes lower on Monday", "url": "https://a.com/4", "published": now.isoformat()},
    ]
    monkeypatch.setattr(nb, "_query_rows", lambda query, locale, max_results: [dict(r) for r in rows])
    taxonomy = {"categories": {"telkom_news": {"queries": ["q"], "max_age_hours": 96, "required_any": ["Telkom"]}}}
    titles = [r["title"] for r in nb._fetch_category("telkom_news", taxonomy, 6)]
    assert titles == ["Telkom expands data center"]


def test_topic_match_uses_whole_word_for_short_terms():
    assert nb._matches_topic({"title": "OpenAI ships new AI agent"}, ["AI"])
    assert not nb._matches_topic({"title": "Minister said the plan is final"}, ["AI"])
    assert nb._matches_topic({"title": "Saham telkom menguat"}, ["Telkom"])


def test_rss_snippet_that_repeats_title_is_removed():
    item = nb._clean_item({"title": "Saham Telkom (TLKM) Kena Revisi - investor.id", "source": "investor.id",
                           "snippet": "Saham Telkom (TLKM) Kena Revisi &nbsp;&nbsp; investor.id"})
    assert item["title"] == "Saham Telkom (TLKM) Kena Revisi" and item["snippet"] == ""


def test_story_is_not_repeated_across_topics(monkeypatch):
    story = {"title": "Saham Telkom (TLKM) Kena Revisi", "url": "https://x.com/tlkm", "source": "investor.id"}
    monkeypatch.setattr(nb, "_fetch_category", lambda c, t, m: [dict(story)] if c in ("telkom_stock", "telkom_news") else [])
    monkeypatch.setattr(nb, "_load_json", lambda path: {"sources": {}} if str(path).endswith("news_sources.json")
                        else {"categories": {c: {"keywords": []} for c in nb.CATEGORY_ORDER}})
    result = nb.collect_news(max_per_category=3)
    assert len(result["telkom_stock"]) == 1 and result["telkom_news"] == []


def test_query_rows_prefers_rss_and_falls_back_to_ddg(monkeypatch):
    import actions.web_search as ws
    monkeypatch.setattr(ws, "_google_news_rss", lambda q, max_results, locale: [])
    monkeypatch.setattr(ws, "_ddg_news", lambda q, max_results: [{"title": "from ddg"}])
    assert nb._query_rows("q", "id", 5) == [{"title": "from ddg"}]


def test_fetch_stock_quote_parses_yahoo_chart(monkeypatch):
    payload = {"chart": {"result": [{"meta": {
        "regularMarketPrice": 2690.0, "currency": "IDR", "exchangeName": "JKT", "chartPreviousClose": 2600.0,
        "regularMarketDayHigh": 2700.0, "regularMarketDayLow": 2640.0, "regularMarketVolume": 1000,
        "regularMarketTime": 1789372200},
        "indicators": {"quote": [{"close": [2610.0, None, 2650.0, 2690.0]}]}}]}}

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return nb.json.dumps(payload).encode()

    monkeypatch.setattr(nb.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    q = nb.fetch_stock_quote("TLKM.JK")
    assert q["price"] == 2690.0 and q["previous_close"] == 2650.0
    assert q["change"] == 40.0 and round(q["change_pct"], 2) == 1.51
    assert q["as_of"].utcoffset() == nb.timedelta(hours=7)


def test_fetch_stock_quote_failure_returns_none(monkeypatch):
    def boom(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(nb.urllib.request, "urlopen", boom)
    assert nb.fetch_stock_quote("TLKM.JK") is None


def test_news_briefing_handles_invalid_max_items(monkeypatch):
    monkeypatch.setattr(nb, "collect_news", lambda max_per_category: {c: [] for c in nb.CATEGORY_ORDER})
    monkeypatch.setattr(nb, "fetch_stock_quote", lambda symbol: None)
    text = nb.news_briefing({"max_items": "not-a-number"})
    assert "NEWS BRIEFING" in text


def test_startup_briefing_returns_title_and_text(monkeypatch):
    monkeypatch.setattr(nb, "collect_news", lambda max_per_category: {c: [] for c in nb.CATEGORY_ORDER})
    monkeypatch.setattr(nb, "fetch_stock_quote", lambda symbol: None)
    title, text = nb.startup_briefing()
    assert "TLKM" in title and "TRENDING TOPIK AI" in text


def test_google_news_redirect_links_are_hidden():
    lines = nb._render_category("Telkom", [
        {"title": "A", "source": "x", "url": "https://news.google.com/rss/articles/CBMi123"},
        {"title": "B", "source": "y", "url": "https://www.telkom.co.id/news/b"},
    ])
    text = "\n".join(lines)
    assert "news.google.com" not in text and "https://www.telkom.co.id/news/b" in text

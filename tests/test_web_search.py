from actions import web_search as ws


def test_google_news_rss_parser(monkeypatch):
    payload = b'''<?xml version="1.0"?><rss><channel><item><title>Test headline</title><link>https://example.com/story</link><description>Test description</description><source>Example</source><pubDate>Sun, 13 Sep 2026 08:00:00 GMT</pubDate></item></channel></rss>'''

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return payload

    monkeypatch.setattr(ws.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    result = ws._google_news_rss("test", max_results=3)
    assert result[0]["title"] == "Test headline"
    assert result[0]["source"] == "Example"
    assert result[0]["published"]


def test_ddg_news_falls_back_to_rss(monkeypatch):
    class BrokenDDGS:
        def __enter__(self):
            raise RuntimeError("provider unavailable")
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(ws, "_ddgs_client", lambda: BrokenDDGS)
    monkeypatch.setattr(ws, "_ddg_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(ws, "_google_news_rss", lambda *args, **kwargs: [{
        "title": "RSS fallback headline",
        "snippet": "fallback",
        "url": "https://example.com/rss",
        "source": "Example",
        "published": "Sun, 13 Sep 2026 08:00:00 GMT",
    }])
    result = ws._ddg_news("test", max_results=3)
    assert result[0]["title"] == "RSS fallback headline"
    assert result[0]["url"] == "https://example.com/rss"

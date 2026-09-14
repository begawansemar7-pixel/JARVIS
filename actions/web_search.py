"""JARVIS web/news retrieval with resilient multi-backend fallback."""
from __future__ import annotations

import json
import re
import sys
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


GEMINI_QUOTA_COOLDOWN_SECONDS = 600
_gemini_blocked_until = 0.0


def _gemini_search(query: str) -> str:
    """Grounded Gemini search. After a quota error (429) Gemini is skipped for a
    while so every search does not burn a failing request before falling back."""
    global _gemini_blocked_until
    import time as _time
    if _time.monotonic() < _gemini_blocked_until:
        raise RuntimeError("Gemini search paused after a quota error; using article search")
    from google import genai
    client = genai.Client(api_key=_get_api_key())
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=query,
            config={"tools": [{"google_search": {}}]},
        )
    except Exception as exc:
        if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
            _gemini_blocked_until = _time.monotonic() + GEMINI_QUOTA_COOLDOWN_SECONDS
            print(f"[WebSearch] Gemini quota exhausted — pausing grounded search for "
                  f"{GEMINI_QUOTA_COOLDOWN_SECONDS // 60} min")
        raise
    text = "".join(
        part.text for part in response.candidates[0].content.parts
        if hasattr(part, "text") and part.text
    ).strip()
    if not text:
        raise ValueError("Gemini returned an empty response.")
    return text


def _ddgs_client():
    try:
        from ddgs import DDGS
        return DDGS
    except ImportError:
        from duckduckgo_search import DDGS
        return DDGS


def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    results = []
    DDGS = _ddgs_client()
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "url": r.get("href", ""),
                "source": r.get("source", ""),
            })
    return results


GOOGLE_NEWS_LOCALES = {
    "en": "hl=en-US&gl=US&ceid=US:en",
    "id": "hl=id&gl=ID&ceid=ID:id",
}


def _google_news_rss(query: str, max_results: int = 8, locale: str = "en") -> list[dict]:
    """Dependency-light news backend using Google News RSS (dated articles)."""
    encoded = urllib.parse.quote(query or "world news")
    params = GOOGLE_NEWS_LOCALES.get(locale, GOOGLE_NEWS_LOCALES["en"])
    url = f"https://news.google.com/rss/search?q={encoded}&{params}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "JARVIS-News/1.0 (+https://github.com/begawansemar7-pixel/JARVIS)"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        root = ET.fromstring(response.read())
    results = []
    for item in root.findall("./channel/item")[:max_results]:
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        description = item.findtext("description", "").strip()
        source_node = item.find("source")
        source = source_node.text.strip() if source_node is not None and source_node.text else ""
        published = item.findtext("pubDate", "").strip()
        if title and link:
            results.append({
                "title": title,
                "snippet": re.sub(r"<[^>]+>", " ", description).strip(),
                "url": link,
                "source": source,
                "published": published,
            })
    return results


def _ddg_news(query: str, max_results: int = 8) -> list[dict]:
    """Return real articles. Fallback chain: DDGS news -> DDG text -> Google News RSS."""
    errors = []
    try:
        DDGS = _ddgs_client()
        with DDGS() as ddgs:
            rows = list(ddgs.news(query, max_results=max_results) or [])
        results = []
        for r in rows:
            url = r.get("url") or r.get("href") or ""
            if not url:
                continue
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", "") or r.get("snippet", ""),
                "url": url,
                "source": r.get("source", ""),
                "published": r.get("date", "") or r.get("published", ""),
            })
        if results:
            return results
    except Exception as exc:
        errors.append(f"DDGS news: {exc}")

    try:
        results = _ddg_search(query, max_results=max_results)
        if results:
            return results
    except Exception as exc:
        errors.append(f"DDGS text: {exc}")

    try:
        results = _google_news_rss(query, max_results=max_results)
        if results:
            print("[WebSearch] ℹ️ Using Google News RSS fallback")
            return results
    except Exception as exc:
        errors.append(f"Google News RSS: {exc}")

    if errors:
        print("[WebSearch] ❌ News backends exhausted: " + " | ".join(errors[-3:]))
    return []


def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"
    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"): lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        if r.get("url"): lines.append(f"   Source: {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_news(query: str, results: list[dict]) -> str:
    if not results:
        return f"No news found for: {query}"
    lines = [f"Latest news: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        if not title:
            continue
        src = f"  [{r['source']}]" if r.get("source") else ""
        lines.append(f"{i}. {title}{src}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:180]}")
        if r.get("url"):
            lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def _gemini_headlines(n: int = 5) -> tuple[list[str], str]:
    import re as _re
    from google import genai
    client = genai.Client(api_key=_get_api_key())
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=f"Current world news: {n} headlines. Numbered list, titles only.",
        config={"tools": [{"google_search": {}}]},
    )
    raw = "".join(
        part.text for part in response.candidates[0].content.parts
        if hasattr(part, "text") and part.text
    ).strip()
    headlines = []
    for line in raw.splitlines():
        line = line.strip()
        if not _re.match(r"^\d+[.\)\-]", line):
            continue
        clean = _re.sub(r"^\d+[.\)\-]\s*", "", line).strip()
        if clean and len(clean) > 10:
            headlines.append(clean)
    return headlines[:n], raw


def _search(query: str) -> str:
    try:
        return _gemini_search(query)
    except Exception as exc:
        print(f"[WebSearch] ⚠️ Gemini failed ({exc}) — trying DDGS...")
        return _format_ddg(query, _ddg_search(query))


def _news(query: str) -> str:
    """Use both grounded Gemini and article retrieval; never depend on one provider."""
    gemini_query = f"latest news today: {query}" if query else "top world news today"
    ddg_query = query or "world news today"
    result_box = [None]
    lock = threading.Lock()
    done = threading.Event()
    failures = [0]

    def store(value: str) -> None:
        if value and len(value) > 60:
            with lock:
                if result_box[0] is None:
                    result_box[0] = value
            done.set()
        else:
            with lock:
                failures[0] += 1
                if failures[0] >= 2:
                    done.set()

    def try_gemini() -> None:
        try:
            store(_gemini_search(gemini_query))
        except Exception as exc:
            print(f"[WebSearch] ⚠️ Gemini news failed ({exc})")
            store("")

    def try_articles() -> None:
        try:
            store(_format_news(ddg_query, _ddg_news(ddg_query, max_results=8)))
        except Exception as exc:
            print(f"[WebSearch] ⚠️ Article news failed ({exc})")
            store("")

    threading.Thread(target=try_gemini, daemon=True).start()
    threading.Thread(target=try_articles, daemon=True).start()
    done.wait(timeout=12.0)
    return result_box[0] or f"No news found for: {query}"


def _research(query: str) -> str:
    prompt = f"Comprehensive, detailed explanation of: {query}. Include background context, key facts, current state, and important nuances."
    try:
        return _gemini_search(prompt)
    except Exception as exc:
        print(f"[WebSearch] ⚠️ Research Gemini failed ({exc}) — DDGS fallback: {exc}")
        return _format_ddg(query, _ddg_search(query, max_results=10))


def _price(query: str) -> str:
    try:
        return _gemini_search(f"current price of {query} — how much does it cost today")
    except Exception as exc:
        print(f"[WebSearch] ⚠️ Price Gemini failed ({exc}) — DDGS fallback")
        return _format_ddg(query, _ddg_search(f"{query} price buy", max_results=6))


def _compare(items: list[str], aspect: str) -> str:
    query = f"Compare {', '.join(items)} in terms of {aspect}. Give specific facts and data."
    try:
        return _gemini_search(query)
    except Exception as exc:
        print(f"[WebSearch] ⚠️ Gemini compare failed ({exc}) — DDGS fallback")
    lines = [f"Comparison — {aspect.upper()}", "─" * 40]
    for item in items:
        lines.append(f"\n▸ {item}")
        for r in _ddg_search(f"{item} {aspect}", max_results=3)[:2]:
            if r.get("snippet"): lines.append(f"  • {r['snippet']}")
            if r.get("url"): lines.append(f"    {r['url']}")
    return "\n".join(lines)


def web_search(parameters: dict, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    query = str(params.get("query", "")).strip()
    mode = str(params.get("mode", "search")).lower().strip()
    items = params.get("items", [])
    aspect = str(params.get("aspect", "general")).strip() or "general"
    if not query and not items:
        return "Please provide a search query."
    if items and mode != "compare":
        mode = "compare"
    if player:
        player.write_log(f"[Search:{mode}] {query or ', '.join(items)}")
    print(f"[WebSearch] 🔍 mode={mode!r} query={query!r}")
    try:
        if mode == "compare" and items: return _compare(items, aspect)
        if mode == "news": return _news(query)
        if mode == "research": return _research(query)
        if mode == "price": return _price(query)
        return _search(query)
    except Exception as exc:
        print(f"[WebSearch] ❌ All backends failed: {exc}")
        return f"Search failed: {exc}"


TOOL = {
    "name": "web_search",
    "description": "Searches the web. Use for current facts, events, prices, or topics. Modes: search, news, research, price, compare. News mode uses Gemini grounded search plus DDGS article search with Google News RSS as an emergency fallback.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "Search query or topic"},
            "mode": {"type": "STRING", "description": "search | news | research | price | compare"},
            "items": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
            "aspect": {"type": "STRING", "description": "Comparison aspect"},
        },
        "required": ["query"],
    },
    "handler": web_search,
}

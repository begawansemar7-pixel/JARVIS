"""JARVIS News Intelligence Engine."""
from __future__ import annotations

import hashlib
import html
import json
import math
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_REGISTRY = BASE_DIR / "config" / "news_sources.json"
TOPIC_TAXONOMY = BASE_DIR / "config" / "news_topics.json"
PROMPT_FILE = BASE_DIR / "config" / "news_executive_prompt.md"
CATEGORY_ORDER = ("telkom_stock", "telkom_news", "ai_trending")
WIB = timezone(timedelta(hours=7))
QUOTE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
        return host.removeprefix("www.")
    except Exception:
        return ""


def _norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9\u00c0-\u024f\u1e00-\u1eff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in _norm(text).split() if len(t) > 2}


def _similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _fingerprints(item: dict) -> set[str]:
    """Return URL and title fingerprints for cross-publisher deduplication."""
    fingerprints = set()
    url = (item.get("url") or "").split("#", 1)[0].rstrip("/").lower()
    title = _norm(item.get("title", ""))
    if url:
        fingerprints.add("url:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16])
    if title:
        fingerprints.add("title:" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:16])
    return fingerprints


def _fingerprint(item: dict) -> str:
    """Return URL fingerprint when available, preserving the historical API."""
    url = (item.get("url") or "").split("#", 1)[0].rstrip("/").lower()
    if url:
        return "url:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    title = _norm(item.get("title", ""))
    return "title:" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:16] if title else "empty"


def _source_weight(item: dict, registry: dict) -> float:
    domain = _domain(item.get("url", ""))
    best = 0.55
    for entries in registry.get("sources", {}).values():
        for source in entries:
            source_domain = str(source.get("domain", "")).lower()
            if source_domain and (domain == source_domain or domain.endswith("." + source_domain)):
                best = max(best, float(source.get("weight", 0.55)))
    return min(1.0, best)


def _parse_published(raw) -> datetime | None:
    """ISO 8601 (DDGS) or RFC 2822 (Google News RSS) → aware datetime."""
    if not raw:
        return None
    text = str(raw).strip()
    for parse in (lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")), parsedate_to_datetime):
        try:
            dt = parse(text)
        except (TypeError, ValueError, IndexError):
            continue
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _age_hours(item: dict) -> float | None:
    dt = _parse_published(item.get("published") or item.get("date") or item.get("published_at"))
    if dt is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)


def _recency_score(item: dict) -> float:
    age_h = _age_hours(item)
    if age_h is None:
        return 0.65
    return max(0.05, math.exp(-age_h / 30.0))


def _keyword_score(item: dict, keywords: list[str]) -> float:
    hay = _norm(f"{item.get('title', '')} {item.get('snippet', '')}")
    if not keywords:
        return 0.5
    hits = sum(1 for k in keywords if _norm(k) in hay)
    return min(1.0, hits / min(5, max(1, len(keywords))))


def _score(item: dict, category: str, taxonomy: dict, registry: dict) -> float:
    cfg = taxonomy["categories"][category]
    source = _source_weight(item, registry)
    recency = _recency_score(item)
    relevance = _keyword_score(item, cfg.get("keywords", []))
    momentum = min(1.0, max(0.0, float(item.get("momentum", 0.5))))
    confirmation = min(1.0, max(0.0, float(item.get("confirmation", 0.5))))
    score = (
        0.25 * recency + 0.20 * source + 0.15 * momentum +
        0.15 * confirmation + 0.15 * relevance + 0.10 * relevance
    )
    return round(score * 100, 2)


def deduplicate(items: list[dict]) -> list[dict]:
    """Remove URL/title duplicates while retaining the strongest scored item."""
    kept: list[dict] = []
    seen: set[str] = set()
    for item in sorted(items, key=lambda x: x.get("score", 0), reverse=True):
        fps = _fingerprints(item)
        if not fps:
            kept.append(item)
            continue
        if any(fp in seen for fp in fps):
            continue
        kept.append(item)
        seen.update(fps)
    return kept


def cluster_events(items: list[dict], threshold: float = 0.52) -> list[dict]:
    clusters: list[dict] = []
    for item in sorted(items, key=lambda x: x.get("score", 0), reverse=True):
        placed = False
        for cluster in clusters:
            if _similarity(item.get("title", ""), cluster["lead"].get("title", "")) >= threshold:
                cluster["items"].append(item)
                source = item.get("source", "")
                if source and source not in cluster["sources"]:
                    cluster["sources"].append(source)
                cluster["confirmation"] = min(1.0, 0.5 + 0.15 * (len(cluster["sources"]) - 1))
                placed = True
                break
        if not placed:
            source = item.get("source", "")
            clusters.append({"lead": item, "items": [item], "sources": [source] if source else [], "confirmation": 0.5})
    return clusters


def _matches_topic(item: dict, required_any: list[str]) -> bool:
    """Title (or snippet) must mention the topic: short tokens such as "AI" need a whole-word, case-sensitive match."""
    if not required_any:
        return True
    text = f"{item.get('title', '')} {item.get('snippet', '')}"
    lowered = text.lower()
    for term in required_any:
        if len(term) <= 3:
            if re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", text):
                return True
        elif term.lower() in lowered:
            return True
    return False


def _clean_item(item: dict) -> dict:
    """Google News titles end with " - Publisher" and its snippet only repeats the title."""
    source = item.get("source", "")
    title = html.unescape(item.get("title", "")).strip()
    if source and title.endswith(f" - {source}"):
        title = title[: -len(source) - 3].rstrip()
    snippet = re.sub(r"\s+", " ", html.unescape(item.get("snippet", ""))).strip()
    if title and snippet.lower().startswith(title.lower()[:40]):
        snippet = ""
    item["title"], item["snippet"] = title, snippet
    return item


def _query_rows(query: str, locale: str, max_results: int) -> list[dict]:
    from actions.web_search import _ddg_news, _google_news_rss
    try:
        rows = _google_news_rss(query, max_results=max_results, locale=locale)
        if rows:
            return rows
    except Exception as exc:
        print(f"[News] Google News RSS failed for {query!r}: {type(exc).__name__}")
    return _ddg_news(query, max_results=max_results)


def _fetch_category(category: str, taxonomy: dict, max_results: int) -> list[dict]:
    cfg = taxonomy["categories"][category]
    max_age = cfg.get("max_age_hours")
    locale = cfg.get("locale", "en")
    queries = cfg.get("queries", [])
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, len(queries))) as pool:
        futures = [pool.submit(_query_rows, q, locale, max_results) for q in queries]
        for query, future in zip(queries, futures):
            try:
                rows = future.result()
            except Exception as exc:
                print(f"[News] source query failed category={category} query={query!r}: {exc}")
                continue
            for raw in rows:
                raw = _clean_item(dict(raw))
                if not raw.get("title") or not raw.get("url"):
                    continue
                age = _age_hours(raw)
                # "Up to date" means dated: undated hits are usually tag or landing pages.
                if max_age and (age is None or age > float(max_age)):
                    continue
                if not _matches_topic(raw, cfg.get("required_any", [])):
                    continue
                raw["category"] = category
                raw["source"] = raw.get("source") or _domain(raw.get("url", ""))
                results.append(raw)
    return results


def _select_category(category: str, raw: list[dict], taxonomy: dict, registry: dict, limit: int) -> list[dict]:
    for item in raw:
        matching_sources = {
            other.get("source", "") for other in raw
            if other is not item and other.get("source", "")
            and other.get("source", "") != item.get("source", "")
            and _similarity(item.get("title", ""), other.get("title", "")) >= 0.52
        }
        item["confirmation"] = min(1.0, 0.5 + 0.15 * len(matching_sources))
        item["score"] = _score(item, category, taxonomy, registry)
    selected = []
    for cluster in cluster_events(deduplicate(raw)):
        lead = dict(cluster["lead"])
        lead["confirmation"] = cluster["confirmation"]
        lead["score"] = _score(lead, category, taxonomy, registry)
        lead["sources"] = cluster["sources"]
        selected.append(lead)
    return sorted(selected, key=lambda x: x.get("score", 0), reverse=True)[:limit]


def collect_news(max_per_category: int = 5) -> dict[str, list[dict]]:
    registry = _load_json(SOURCE_REGISTRY)
    taxonomy = _load_json(TOPIC_TAXONOMY)
    fetch_size = max(6, max_per_category + 2)
    # Categories are independent network work: fetch them in parallel so the
    # startup briefing is not three times slower than one search.
    with ThreadPoolExecutor(max_workers=len(CATEGORY_ORDER)) as pool:
        futures = {c: pool.submit(_fetch_category, c, taxonomy, fetch_size) for c in CATEGORY_ORDER}
        raw = {c: f.result() for c, f in futures.items()}
    output: dict[str, list[dict]] = {}
    shown: set[str] = set()
    for c in CATEGORY_ORDER:   # a story already listed under an earlier topic is not repeated
        fresh = [item for item in raw[c] if not (_fingerprints(item) & shown)]
        output[c] = _select_category(c, fresh, taxonomy, registry, max_per_category)
        for item in output[c]:
            shown.update(_fingerprints(item))
    return output


# -- stock quote ------------------------------------------------------------------------

def fetch_stock_quote(symbol: str = "TLKM.JK", timeout: float = 8.0) -> dict | None:
    """Latest daily quote from Yahoo Finance's public chart endpoint (no API key).

    Returns None when the quote cannot be fetched; the briefing then says so instead
    of guessing a price."""
    url = QUOTE_URL.format(symbol=quote(symbol))
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (JARVIS news briefing)"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
        result = payload["chart"]["result"][0]
        meta = result["meta"]
        price = float(meta["regularMarketPrice"])
    except Exception as exc:
        print(f"[News] stock quote failed for {symbol}: {type(exc).__name__}")
        return None

    closes = [c for c in (result.get("indicators", {}).get("quote", [{}])[0].get("close") or []) if c is not None]
    # Previous session close: the second-to-last daily close when today's bar exists.
    previous = float(closes[-2]) if len(closes) >= 2 else meta.get("chartPreviousClose")
    change = (price - float(previous)) if previous else None
    market_time = meta.get("regularMarketTime")
    return {
        "symbol": symbol,
        "price": price,
        "currency": meta.get("currency", ""),
        "previous_close": float(previous) if previous else None,
        "change": change,
        "change_pct": (change / float(previous) * 100) if change is not None and previous else None,
        "day_high": meta.get("regularMarketDayHigh"),
        "day_low": meta.get("regularMarketDayLow"),
        "volume": meta.get("regularMarketVolume"),
        "as_of": datetime.fromtimestamp(market_time, WIB) if market_time else None,
        "exchange": meta.get("exchangeName", ""),
    }


def _idr(value) -> str:
    return f"{value:,.0f}".replace(",", ".") if value is not None else "-"


def render_quote(q: dict | None, display: str = "TLKM") -> list[str]:
    if not q:
        return ["- Harga saham tidak dapat diambil saat ini; cek aplikasi sekuritas atau idx.co.id."]
    arrow = "▲" if (q["change"] or 0) > 0 else "▼" if (q["change"] or 0) < 0 else "■"
    change = (f"{arrow} {q['change']:+,.0f} ({q['change_pct']:+.2f}%)".replace(",", ".")
              if q["change"] is not None else "perubahan tidak tersedia")
    as_of = q["as_of"].strftime("%d %b %Y %H:%M WIB") if q.get("as_of") else "waktu tidak diketahui"
    lines = [f"- {display} {q['currency']} {_idr(q['price'])}  {change} · penutupan sebelumnya {_idr(q['previous_close'])}"]
    if q.get("day_low") is not None and q.get("day_high") is not None:
        vol = f" · volume {_idr(q['volume'])} lembar" if q.get("volume") else ""
        lines.append(f"- Rentang hari ini {_idr(q['day_low'])}–{_idr(q['day_high'])}{vol}")
    lines.append(f"- Data per {as_of} (Yahoo Finance, dapat tertunda ±15 menit). Bukan rekomendasi investasi.")
    return lines


# -- rendering --------------------------------------------------------------------------

def _render_category(label: str, items: list[dict]) -> list[str]:
    lines = [f"\n{label.upper()}"]
    if not items:
        lines.append("- Tidak ada berita terbaru yang cukup kuat dari sumber yang tersedia.")
        return lines
    for idx, item in enumerate(items, 1):
        title = item.get("title", "Untitled").strip()
        snippet = re.sub(r"\s+", " ", item.get("snippet", "")).strip()[:240]
        source = ", ".join(item.get("sources") or [item.get("source", "")])
        age = _age_hours(item)
        when = (" · baru saja" if age is not None and age < 1
                else f" · {int(age)} jam lalu" if age is not None and age < 72 else "")
        lines.append(f"{idx}. {title} — {source}{when}")
        if snippet:
            lines.append(f"   {snippet}")
        url = item.get("url", "")
        if url and "news.google.com/" not in url:   # Google News redirect links are unreadable
            lines.append(f"   {url}")
    return lines


def render_briefing(data: dict[str, list[dict]], quote: dict | None = None) -> str:
    taxonomy = _load_json(TOPIC_TAXONOMY)
    labels = {c: taxonomy["categories"][c]["label"] for c in CATEGORY_ORDER}
    display = taxonomy.get("stock", {}).get("display", "TLKM")
    lines = ["JARVIS — NEWS BRIEFING", "", f"Fokus: {labels['telkom_stock']} · {labels['telkom_news']} · {labels['ai_trending']}"]

    lines.append(f"\n📈 {labels['telkom_stock'].upper()}")
    lines.extend(render_quote(quote, display))
    stock_news = _render_category("Berita saham", data.get("telkom_stock", []))
    lines.extend(stock_news[1:] if data.get("telkom_stock") else [])
    lines.extend(_render_category(f"📡 {labels['telkom_news']}", data.get("telkom_news", [])))
    lines.extend(_render_category(f"🤖 {labels['ai_trending']}", data.get("ai_trending", [])))

    lines += ["\n🎯 WHAT MATTERS"]
    if quote and quote.get("change_pct") is not None:
        lines.append(f"- {display} {'naik' if quote['change'] > 0 else 'turun' if quote['change'] < 0 else 'stagnan'} "
                     f"{abs(quote['change_pct']):.2f}% dibanding penutupan sebelumnya.")
    if data.get("telkom_news"):
        lines.append(f"- Telkom: {data['telkom_news'][0].get('title', '')}")
    if data.get("ai_trending"):
        lines.append(f"- AI: {data['ai_trending'][0].get('title', '')}")
    lines.append("- Verifikasi angka dan berita penting dari sumber aslinya sebelum mengambil keputusan.")
    return "\n".join(lines)


def startup_briefing(max_items: int = 3) -> tuple[str, str]:
    """(panel title, text) for the startup briefing: TLKM quote + Telkom news + AI trends."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        news_f = pool.submit(collect_news, max_items)
        quote_f = pool.submit(fetch_stock_quote, _load_json(TOPIC_TAXONOMY).get("stock", {}).get("symbol", "TLKM.JK"))
        data, q = news_f.result(), quote_f.result()
    return "NEWS — TLKM · TELKOM · AI", render_briefing(data, q)


def news_briefing(parameters: dict, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    try:
        max_items = int(params.get("max_items", 5))
    except (TypeError, ValueError):
        max_items = 5
    max_items = max(1, min(10, max_items))
    try:
        _, result = startup_briefing(max_items)
        if player:
            player.write_log("[NewsBriefing] generated TLKM + Telkom + AI briefing")
        return result
    except Exception as exc:
        print(f"[News] ❌ briefing failed: {exc}")
        return "News briefing gagal mengambil data secara lengkap. Coba lagi sebentar lagi."


TOOL = {
    "name": "news_briefing",
    "description": (
        "Executive news briefing on the user's three standing topics: (1) Telkom Indonesia stock TLKM "
        "up to date — live quote with change, day range and volume plus stock news; (2) latest news about "
        "Telkom Indonesia and TelkomGroup; (3) trending AI news. Trigger for berita hari ini, berita terbaru, "
        "what's the news, news briefing, update saham Telkom, harga TLKM. Report prices exactly as returned "
        "with their timestamp; never invent a price and never give investment advice."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "max_items": {"type": "INTEGER", "description": "Maximum stories per topic; default 5."}
        },
        "required": []
    },
    "handler": news_briefing,
}

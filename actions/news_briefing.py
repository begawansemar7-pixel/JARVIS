"""JARVIS News Intelligence Engine.

Fetches current news through the existing web-search backend, then applies
category-aware scoring, URL/title deduplication, event clustering, and an
executive-oriented rendering layer. No new third-party dependency is required.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_REGISTRY = BASE_DIR / "config" / "news_sources.json"
TOPIC_TAXONOMY = BASE_DIR / "config" / "news_topics.json"
PROMPT_FILE = BASE_DIR / "config" / "news_executive_prompt.md"

CATEGORY_ORDER = ("id_trending", "ai_global", "ai_indonesia", "telecom_telkom")


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


def _fingerprint(item: dict) -> str:
    url = (item.get("url") or "").split("#", 1)[0].rstrip("/").lower()
    if url:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return hashlib.sha1(_norm(item.get("title", "")).encode("utf-8")).hexdigest()[:16]


def _source_weight(item: dict, registry: dict) -> float:
    domain = _domain(item.get("url", ""))
    best = 0.55
    for entries in registry.get("sources", {}).values():
        for source in entries:
            if domain == source.get("domain") or domain.endswith("." + source.get("domain", "")):
                best = max(best, float(source.get("weight", 0.55)))
    return min(1.0, best)


def _recency_score(item: dict) -> float:
    """Use provider timestamps when present; otherwise give a safe neutral score."""
    raw = item.get("published") or item.get("date") or item.get("published_at")
    if not raw:
        return 0.65
    try:
        value = str(raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_h = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)
        return max(0.05, math.exp(-age_h / 30.0))
    except Exception:
        return 0.65


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
    momentum = float(item.get("momentum", 0.5))
    confirmation = float(item.get("confirmation", 0.5))
    # Executive ranking: recency 25%, authority 20%, momentum 15%, confirmation 15%,
    # strategic relevance 15%, user/topic relevance 10%.
    score = (
        0.25 * recency +
        0.20 * source +
        0.15 * momentum +
        0.15 * confirmation +
        0.15 * relevance +
        0.10 * relevance
    )
    return round(score * 100, 2)


def deduplicate(items: list[dict]) -> list[dict]:
    """Remove exact URL/title duplicates while retaining the strongest source."""
    by_fp: dict[str, dict] = {}
    for item in items:
        fp = _fingerprint(item)
        current = by_fp.get(fp)
        if current is None or item.get("score", 0) > current.get("score", 0):
            by_fp[fp] = item
    return list(by_fp.values())


def cluster_events(items: list[dict], threshold: float = 0.52) -> list[dict]:
    """Greedily cluster near-identical headlines into events for executive display."""
    clusters: list[dict] = []
    for item in sorted(items, key=lambda x: x.get("score", 0), reverse=True):
        placed = False
        for cluster in clusters:
            if _similarity(item.get("title", ""), cluster["lead"].get("title", "")) >= threshold:
                cluster["items"].append(item)
                cluster["sources"] = sorted(set(cluster["sources"] + [item.get("source", "")]))
                cluster["confirmation"] = min(1.0, 0.5 + 0.15 * (len(cluster["items"]) - 1))
                placed = True
                break
        if not placed:
            clusters.append({
                "lead": item,
                "items": [item],
                "sources": [item.get("source", "")],
                "confirmation": 0.5,
            })
    return clusters


def _fetch_category(category: str, taxonomy: dict, max_results: int) -> list[dict]:
    from actions.web_search import _ddg_news

    results: list[dict] = []
    for query in taxonomy["categories"][category].get("queries", []):
        try:
            for raw in _ddg_news(query, max_results=max_results):
                if not raw.get("title") or not raw.get("url"):
                    continue
                raw["category"] = category
                raw["source"] = raw.get("source") or _domain(raw.get("url", ""))
                results.append(raw)
        except Exception as exc:
            print(f"[News] source query failed category={category}: {exc}")
    return results


def collect_news(max_per_category: int = 5) -> dict[str, list[dict]]:
    registry = _load_json(SOURCE_REGISTRY)
    taxonomy = _load_json(TOPIC_TAXONOMY)
    output: dict[str, list[dict]] = {}
    for category in CATEGORY_ORDER:
        raw = _fetch_category(category, taxonomy, max_results=max(6, max_per_category + 2))
        # Apply cross-source confirmation before final ranking.
        for item in raw:
            same_event = sum(
                1 for other in raw
                if other is not item and _similarity(item.get("title", ""), other.get("title", "")) >= 0.52
            )
            item["confirmation"] = min(1.0, 0.5 + 0.15 * same_event)
            item["score"] = _score(item, category, taxonomy, registry)
        unique = deduplicate(raw)
        clusters = cluster_events(unique)
        selected = []
        for cluster in clusters:
            lead = dict(cluster["lead"])
            lead["confirmation"] = cluster["confirmation"]
            lead["score"] = _score(lead, category, taxonomy, registry)
            lead["sources"] = [s for s in cluster["sources"] if s]
            selected.append(lead)
        output[category] = sorted(selected, key=lambda x: x.get("score", 0), reverse=True)[:max_per_category]
    return output


def _render_category(label: str, items: list[dict]) -> list[str]:
    lines = [f"\n### {label}"]
    if not items:
        lines.append("- Tidak ada hasil yang cukup kuat dari sumber yang tersedia.")
        return lines
    for idx, item in enumerate(items, 1):
        title = item.get("title", "Untitled").strip()
        snippet = re.sub(r"\s+", " ", item.get("snippet", "")).strip()[:240]
        source = ", ".join(item.get("sources") or [item.get("source", "")])
        score = item.get("score", 0)
        lines.append(f"{idx}. **{title}** — {source} · score {score}/100")
        if snippet:
            lines.append(f"   {snippet}")
        if item.get("url"):
            lines.append(f"   {item['url']}")
    return lines


def render_briefing(data: dict[str, list[dict]]) -> str:
    labels = {
        "id_trending": "🇮🇩 Trending Indonesia",
        "ai_global": "🤖 AI Global",
        "ai_indonesia": "🇮🇩 AI Indonesia",
        "telecom_telkom": "📡 Telekomunikasi & Telkom",
    }
    all_items = [x for items in data.values() for x in items]
    lines = ["JARVIS — NEWS INTELLIGENCE BRIEFING", "", "Fokus: Indonesia · AI Global · AI Indonesia · Telekomunikasi/Telkom"]
    for category in CATEGORY_ORDER:
        lines.extend(_render_category(labels[category], data.get(category, [])))

    telkom = data.get("telecom_telkom", [])
    ai = data.get("ai_global", []) + data.get("ai_indonesia", [])
    lines += ["\n### 🎯 What matters", "- Prioritaskan event dengan skor tinggi dan konfirmasi lintas sumber."]
    if telkom:
        lines.append(f"- Telkom watch: {telkom[0].get('title', 'No leading Telkom item')}")
    if ai:
        lines.append(f"- AI watch: {ai[0].get('title', 'No leading AI item')}")
    lines += ["- Gunakan link sumber untuk verifikasi sebelum mengambil keputusan.", "\n### ⚠️ Watch next", "- Perubahan regulasi AI/digital di Indonesia.", "- Perkembangan fiber, data center, cloud, AI dan portfolio Telkom.", "- Event yang berubah dari single-source menjadi multi-source confirmation."]
    confidence = "High" if len(all_items) >= 12 else "Medium" if len(all_items) >= 5 else "Low"
    lines += [f"\n### Confidence: {confidence}", "Ranking bersifat heuristik; artikel yang diringkas tetap harus diverifikasi dari sumber aslinya."]
    return "\n".join(lines)


def news_briefing(parameters: dict, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    max_items = max(1, min(10, int(params.get("max_items", 5))))
    try:
        data = collect_news(max_per_category=max_items)
        result = render_briefing(data)
        if player:
            player.write_log("[NewsBriefing] generated Indonesia + AI + Telkom briefing")
        return result
    except Exception as exc:
        print(f"[News] ❌ briefing failed: {exc}")
        return "News briefing gagal mengambil data secara lengkap. Coba lagi; backend berita diisolasi per kategori agar satu sumber gagal tidak mematikan seluruh briefing."


TOOL = {
    "name": "news_briefing",
    "description": (
        "Executive current-news briefing. Trigger this action for commands such as "
        '"what\'s the news", "what is the news", "berita hari ini", "berita terbaru", or "news briefing". '
        "Always cover four sections: Trending Indonesia; AI Global; AI Indonesia; and Telecommunications/Telkom Indonesia. "
        "Use the configured source registry, rank by recency/source authority/topic momentum/cross-source confirmation/strategic relevance, "
        "deduplicate and cluster repeated coverage, then present concise executive implications and watch-next items."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "max_items": {
                "type": "INTEGER",
                "description": "Maximum number of event clusters per section; default 5."
            }
        },
        "required": []
    },
    "handler": news_briefing,
}

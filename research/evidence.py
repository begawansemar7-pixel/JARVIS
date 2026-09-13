"""Evidence gathering for consulting-grade research.

For every issue-tree question:

    web + news search -> dedupe by URL -> credibility tier -> fetch top pages
    -> extract the most relevant, preferably quantitative, sentences
    -> triangulation check (independent domains)

Fetched pages are untrusted data. Only public http(s) hosts are fetched: any URL
resolving to a loopback, private, link-local or reserved address is refused so
a search result cannot make JARVIS probe the local network.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .sources import Credibility, credibility, domain_of

MAX_QUESTIONS = 10
RESULTS_PER_SEARCH = 6
PAGES_PER_QUESTION = 3
FETCH_TIMEOUT = 8
MAX_PAGE_BYTES = 1_500_000
DEADLINE_SECONDS = 45
USER_AGENT = "Mozilla/5.0 (compatible; JARVIS-Research/1.0)"

_WORD = re.compile(r"\w{3,}", re.UNICODE)
_QUANT = re.compile(r"\d|%|\bRp\b|US\$|\$|€|£|miliar|triliun|juta|billion|million|trillion", re.I)
_STOPWORDS = {
    "the", "and", "for", "with", "what", "how", "why", "which", "who", "are", "was", "will", "does",
    "yang", "dan", "untuk", "dengan", "apa", "bagaimana", "mengapa", "dari", "pada", "dalam", "akan",
}


@dataclass
class Source:
    ref: str
    title: str
    url: str
    domain: str
    credibility: Credibility
    published: str = ""
    snippet: str = ""
    excerpts: list[str] = field(default_factory=list)
    fetched: bool = False


@dataclass
class QuestionEvidence:
    question: str
    sources: list[Source]
    independent_domains: int
    triangulated: bool
    note: str = ""


@dataclass
class EvidencePack:
    key_question: str
    questions: list[QuestionEvidence]
    elapsed_seconds: float


# -- backends (monkeypatched in tests) -------------------------------------------

def search_web(query: str, max_results: int) -> list[dict]:
    from actions.web_search import _ddg_search
    return _ddg_search(query, max_results=max_results)


def search_news(query: str, max_results: int) -> list[dict]:
    from actions.web_search import _ddg_news
    return _ddg_news(query, max_results=max_results)


def is_public_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except (socket.gaierror, UnicodeError, ValueError):
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            return False
    return bool(infos)


class _NoPrivateRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_public_http_url(newurl):
            raise urllib.error.URLError("redirect to a non-public address refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_page(url: str) -> str:
    if not is_public_http_url(url):
        raise ValueError("non-public or unsupported URL")
    opener = urllib.request.build_opener(_NoPrivateRedirects)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"})
    with opener.open(request, timeout=FETCH_TIMEOUT) as response:
        ctype = response.headers.get("Content-Type", "")
        if "html" not in ctype and "text" not in ctype:
            raise ValueError(f"unsupported content type {ctype.split(';')[0]}")
        raw = response.read(MAX_PAGE_BYTES + 1)[:MAX_PAGE_BYTES]
        charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


# -- text processing ----------------------------------------------------------------

def html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg"]):
            tag.decompose()
        text = soup.get_text("\n")
    except ImportError:
        text = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
        text = re.sub(r"<[^>]+>", "\n", text)
    return re.sub(r"[ \t\r\f\v]+", " ", text)


def _terms(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)} - _STOPWORDS


def _looks_like_heading(s: str) -> bool:
    """Page titles and menu lines: no sentence ending and mostly Capitalised Words."""
    words = [w for w in re.findall(r"[^\W\d_]+", s)]
    if len(words) < 6:
        return True
    capitalised = sum(1 for w in words if w[0].isupper())
    return not s.rstrip().endswith((".", "!", "?", "…")) and capitalised / len(words) > 0.5


def extract_excerpts(text: str, question: str, limit: int = 3, max_len: int = 320) -> list[str]:
    """Pick the sentences that best answer the question, favouring quantitative ones."""
    q = _terms(question)
    if not q:
        return []
    candidates = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        s = sentence.strip()
        if not 40 <= len(s) <= 600 or _looks_like_heading(s):
            continue
        overlap = len(q & _terms(s))
        if overlap == 0:
            continue
        score = overlap / len(q) + (0.35 if _QUANT.search(s) else 0.0)
        candidates.append((score, s))
    candidates.sort(key=lambda c: c[0], reverse=True)
    out, seen = [], set()
    for _score, s in candidates:
        key = s.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(s if len(s) <= max_len else s[: max_len - 1].rstrip() + "…")
        if len(out) >= limit:
            break
    return out


# -- orchestration ------------------------------------------------------------------

def _query(question: str, context: str) -> str:
    return f"{question} {context}".strip()


def _collect(question: str, context: str, include_news: bool) -> list[dict]:
    rows = []
    for backend in (search_web, search_news) if include_news else (search_web,):
        try:
            rows.extend(backend(_query(question, context), RESULTS_PER_SEARCH) or [])
        except Exception as e:  # one backend failing must not sink the question
            print(f"[Research] {backend.__name__} failed: {type(e).__name__}")
    unique, seen = [], set()
    for r in rows:
        url = str(r.get("url") or r.get("href") or "").split("#", 1)[0]
        if not url or url in seen or not url.startswith(("http://", "https://")):
            continue
        seen.add(url)
        unique.append({**r, "url": url})
    return unique


def _gather_question(question: str, context: str, include_news: bool, deadline: float) -> QuestionEvidence:
    rows = _collect(question, context, include_news)
    sources = [
        Source(ref="", title=str(r.get("title") or domain_of(r["url"])).strip(), url=r["url"],
               domain=domain_of(r["url"]), credibility=credibility(r["url"]),
               published=str(r.get("published") or ""), snippet=str(r.get("snippet") or "").strip())
        for r in rows
    ]
    sources.sort(key=lambda s: s.credibility.weight, reverse=True)

    for source in sources[:PAGES_PER_QUESTION]:
        if time.monotonic() > deadline:
            break
        try:
            source.excerpts = extract_excerpts(html_to_text(fetch_page(source.url)), question)
            source.fetched = True
        except Exception:
            pass
    for source in sources:
        if not source.excerpts and source.snippet and not _looks_like_heading(source.snippet):
            source.excerpts = [source.snippet[:320]]

    usable = [s for s in sources if s.excerpts]
    domains = {s.domain for s in usable}
    strong = {s.domain for s in usable if s.credibility.weight >= 0.75}
    triangulated = len(domains) >= 2 and len(strong) >= 1
    note = ""
    if not usable:
        note = "[DATA GAP] no usable evidence found"
    elif not triangulated:
        note = "[TRIANGULATION GAP] fewer than two independent sources or no T1–T3 source"
    return QuestionEvidence(question, usable[:8], len(domains), triangulated, note)


def gather_evidence(key_question: str, questions: list[str], context: str = "",
                    include_news: bool = True) -> EvidencePack:
    questions = [q.strip() for q in questions if q and q.strip()][:MAX_QUESTIONS]
    if not questions:
        raise ValueError("provide at least one issue-tree question")
    started = time.monotonic()
    deadline = started + DEADLINE_SECONDS
    results: dict[int, QuestionEvidence] = {}
    with ThreadPoolExecutor(max_workers=min(4, len(questions))) as pool:
        futures = {pool.submit(_gather_question, q, context, include_news, deadline): i
                   for i, q in enumerate(questions)}
        for future in as_completed(futures):
            i = futures[future]
            try:
                results[i] = future.result()
            except Exception as e:
                results[i] = QuestionEvidence(questions[i], [], 0, False,
                                              f"[DATA GAP] gathering failed ({type(e).__name__})")

    ordered = [results[i] for i in range(len(questions))]
    counter = 0
    by_url: dict[str, str] = {}
    for qe in ordered:  # stable [S#] references, shared when a URL answers several questions
        for s in qe.sources:
            if s.url not in by_url:
                counter += 1
                by_url[s.url] = f"S{counter}"
            s.ref = by_url[s.url]
    return EvidencePack(key_question.strip(), ordered, round(time.monotonic() - started, 1))


__all__ = ["EvidencePack", "QuestionEvidence", "Source", "extract_excerpts", "fetch_page",
           "gather_evidence", "html_to_text", "is_public_http_url"]

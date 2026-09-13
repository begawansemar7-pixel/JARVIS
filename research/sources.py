"""Source credibility tiers for evidence gathering (config/research_sources.json)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCES_PATH = BASE_DIR / "config" / "research_sources.json"


@dataclass(frozen=True)
class Credibility:
    tier: str
    label: str
    weight: float


def domain_of(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


@lru_cache(maxsize=4)
def _registry(path: str = str(SOURCES_PATH)) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def credibility(url: str, registry: dict | None = None) -> Credibility:
    reg = registry or _registry()
    domain = domain_of(url)
    best: tuple[int, Credibility] | None = None
    for tier in reg.get("tiers", []):
        for pattern in tier.get("domains", []):
            p = pattern.lower()
            matched = domain.endswith(p) if p.startswith(".") else (domain == p or domain.endswith("." + p))
            if matched:
                # The most specific (longest) pattern wins, so "brin.go.id" beats ".go.id".
                candidate = (len(p), Credibility(tier["tier"], tier["label"], float(tier["weight"])))
                if best is None or candidate[0] > best[0]:
                    best = candidate
    if best:
        return best[1]
    return Credibility("T4", "General web", float(reg.get("default_weight", 0.5)))


__all__ = ["Credibility", "credibility", "domain_of"]

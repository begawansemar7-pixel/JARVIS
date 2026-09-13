"""Consulting-grade research: evidence gathering, source credibility and market sizing."""

from .evidence import EvidencePack, gather_evidence
from .sizing import parse_drivers, size_market
from .sources import credibility

__all__ = ["EvidencePack", "credibility", "gather_evidence", "parse_drivers", "size_market"]

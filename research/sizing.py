"""Deterministic market sizing with scenarios and one-at-a-time sensitivity.

The model supplies drivers (and their sources); arithmetic is done here so a
voice model never multiplies large numbers in its head.

    size = driver_1 × driver_2 × … × driver_n

Each driver has low / base / high values. Scenarios multiply all lows, all bases
and all highs; the sensitivity ("tornado") varies one driver between its low and
high while holding the rest at base, ranked by the swing it causes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Driver:
    name: str
    low: float
    base: float
    high: float
    unit: str = ""
    source: str = ""


@dataclass(frozen=True)
class SizingResult:
    low: float
    base: float
    high: float
    sensitivity: list[tuple[str, float, float, float]]  # name, value at low, value at high, swing
    drivers: list[Driver]


def _number(value, field: str) -> float:
    try:
        number = float(str(value).replace(",", "").replace("_", ""))
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number") from None
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a finite, non-negative number")
    return number


def parse_drivers(raw) -> list[Driver]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("drivers must be a non-empty list")
    if len(raw) > 12:
        raise ValueError("use at most 12 drivers")
    drivers = []
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict) or not str(item.get("name") or "").strip():
            raise ValueError(f"driver {i} needs a name")
        name = str(item["name"]).strip()
        base = _number(item.get("base"), f"{name}.base")
        low = _number(item.get("low", base), f"{name}.low")
        high = _number(item.get("high", base), f"{name}.high")
        if not low <= base <= high:
            raise ValueError(f"{name}: expected low ≤ base ≤ high")
        drivers.append(Driver(name, low, base, high, str(item.get("unit") or ""), str(item.get("source") or "")))
    return drivers


def size_market(drivers: list[Driver]) -> SizingResult:
    base = math.prod(d.base for d in drivers)
    sensitivity = []
    for d in drivers:
        others = math.prod(o.base for o in drivers if o is not d)
        at_low, at_high = others * d.low, others * d.high
        sensitivity.append((d.name, at_low, at_high, at_high - at_low))
    sensitivity.sort(key=lambda row: row[3], reverse=True)
    return SizingResult(
        low=math.prod(d.low for d in drivers),
        base=base,
        high=math.prod(d.high for d in drivers),
        sensitivity=sensitivity,
        drivers=drivers,
    )


def human(value: float) -> str:
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= threshold:
            return f"{value / threshold:,.2f}{suffix}"
    return f"{value:,.2f}"


__all__ = ["Driver", "SizingResult", "human", "parse_drivers", "size_market"]

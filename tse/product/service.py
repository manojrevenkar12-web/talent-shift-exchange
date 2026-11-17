"""Erlang C: how many talents a half hour needs to answer the target share of calls in time."""
from __future__ import annotations

import math


def erlang_c(n: int, a: float) -> float:
    if n <= a:
        return 1.0
    s, term = 1.0, 1.0
    for k in range(1, n):
        term *= a / k
        s += term
    term *= a / n
    top = term * n / (n - a)
    return top / (s + top)


def service_level(n: int, calls: float, aht_s: float, interval_s: float, within_s: float) -> float:
    if calls <= 0:
        return 1.0
    a = calls * aht_s / interval_s
    if n <= a:
        return 0.0
    return 1 - erlang_c(n, a) * math.exp(-(n - a) * within_s / aht_s)


def agents_needed(calls: float, aht_s: float, cfg: dict) -> int:
    s = cfg["service"]
    if calls <= 0:
        return 0
    n = max(1, int(calls * aht_s / s["interval_s"]))
    while service_level(n, calls, aht_s, s["interval_s"], s["answer_within_s"]) < s["target_share"]:
        n += 1
    return math.ceil(n / (1 - s["shrinkage"]))

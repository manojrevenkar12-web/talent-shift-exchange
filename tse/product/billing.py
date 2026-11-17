"""Pay for productive time only, exactly once. Events from the talents' apps arrive twice, late and out of order,
with skewed clocks, and some sessions never send a logout. Events are folded per session by the app's sequence
number, not by arrival or by timestamp."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass
class Statement:
    talent: str
    period: str
    productive_s: int
    cents: int
    sessions: int
    open_calls: int                 # a call that started and never ended (the app died mid-call): not paid, reported


def session_key(e: dict) -> str:
    return e["id"].rsplit("-", 1)[0]


def session_week(e: dict) -> int:
    """The app names each event talent-week-day-shift-seq; a session's pay belongs to the week it was worked."""
    return int(session_key(e).rsplit("-", 3)[1])


def fold(events: list[dict], acw_cap: dict[str, int]) -> dict[str, dict]:
    """session -> productive seconds, from deduplicated events in sequence order."""
    seen, sessions = set(), defaultdict(list)
    for e in events:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        sessions[session_key(e)].append(e)
    out = {}
    for key, evs in sessions.items():
        evs.sort(key=lambda e: e["seq"])
        prod, open_calls, start, end = 0, 0, None, None
        for e in evs:
            if e["kind"] == "call_start":
                if start is not None:
                    open_calls += 1
                start, end = e["ts"], None
            elif e["kind"] == "call_end" and start is not None:
                end = e["ts"]
            elif e["kind"] == "acw_end" and start is not None and end is not None:
                cap = acw_cap.get(e["project"], 0)
                prod += max(0, end - start) + min(max(0, e["ts"] - end), cap)
                start = end = None
        if start is not None and end is not None:      # the app died during after-call work: pay the talk
            prod += max(0, end - start)
        elif start is not None:
            open_calls += 1
        out[key] = {"talent": evs[0]["talent"], "productive_s": prod, "open_calls": open_calls}
    return out


def statements(events: list[dict], period: str, cfg: dict) -> dict[str, Statement]:
    caps = {p: v["acw_cap_s"] for p, v in cfg["projects"].items()}
    rate = cfg["billing"]["eur_per_productive_min"]
    per = defaultdict(lambda: [0, 0, 0])
    for s in fold(events, caps).values():
        per[s["talent"]][0] += s["productive_s"]
        per[s["talent"]][1] += 1
        per[s["talent"]][2] += s["open_calls"]
    return {t: Statement(t, period, v[0], int(round(v[0] / 60 * rate * 100)), v[1], v[2]) for t, v in per.items()}

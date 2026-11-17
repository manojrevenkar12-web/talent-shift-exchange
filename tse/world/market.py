"""The simulated marketplace: client projects and their call volume, the freelance talents and what they want, who
shows up, call transcripts with the guidelines they did or did not follow, and the raw event streams the talents'
apps send. Everything the product is scored against is made here; the product never imports this module."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from tse.keyed import rng

DAYS = 7


@dataclass
class Talent:
    id: str
    languages: list[str]
    certified: list[str]
    noshow: float
    hours_week: int
    quality: float
    likes: set                     # (day, shift index) the talent would work


@dataclass
class World:
    name: str
    cfg: dict
    projects: dict
    talents: list[Talent]
    weeks: int
    intervals: list[tuple[int, int]] = field(default_factory=list)   # (hour, minute) starts

    def interval_index(self, hour: int, minute: int = 0) -> int:
        return self.intervals.index((hour, minute))


def load(path: str | Path, quick: bool = False) -> World:
    cfg = yaml.safe_load(Path(path).read_text())
    o = cfg["open"]
    ivs = [(h, m) for h in range(o["from_hour"], o["to_hour"]) for m in range(0, 60, o["interval_min"])]
    w = World(cfg["name"], cfg, cfg["projects"], [], cfg["quick_weeks"] if quick else cfg["weeks"], ivs)
    t = cfg["talents"]
    r = rng(cfg["seed"], "talents")
    langs = list(t["languages"])
    for i in range(t["count"]):
        spoken = [x for x in langs if r.random() < t["languages"][x]] or [langs[int(r.integers(len(langs)))]]
        eligible = [p for p, v in cfg["projects"].items() if v["language"] in spoken]
        k = int(r.integers(t["certified_per_talent"][0], t["certified_per_talent"][1] + 1))
        cert = [str(x) for x in r.permutation(eligible)[:k]] if eligible else []
        likes = {(d, s) for d in range(DAYS) for s in range(len(cfg["shifts"])) if r.random() < 0.35}
        w.talents.append(Talent(f"T{i:04d}", spoken, cert, float(r.uniform(*t["noshow"])),
                                int(r.integers(t["hours_week"][0], t["hours_week"][1] + 1)),
                                float(r.uniform(*t["quality"])), likes))
    return w


# ---------------------------------------------------------------- demand

def mean_calls(w: World, project: str, week: int, day: int, iv: int, surges: bool = True) -> float:
    p = w.projects[project]
    h, m = w.intervals[iv]
    t = h + m / 60
    shape = 0.55 + 0.6 * math.exp(-((t - 10.5) ** 2) / 3) + 0.45 * math.exp(-((t - 15.5) ** 2) / 4)
    dayf = [1.15, 1.0, 0.95, 0.95, 1.05, p["weekend"], p["weekend"] * 0.8][day]
    trend = 1 + 0.01 * week
    mu = p["base"] * shape * dayf * trend
    if surges:
        for s in w.cfg["surges"]:
            same_day = s["project"] == project and s["week"] + w.cfg["history_weeks"] == week and s["day"] == day
            if same_day and s["from_hour"] <= t < s["from_hour"] + s["hours"]:
                mu *= s["factor"]
    return mu


def calls(w: World, project: str, week: int, day: int, iv: int) -> int:
    return int(rng(w.name, "calls", project, week, day, iv).poisson(mean_calls(w, project, week, day, iv)))


# ---------------------------------------------------------------- talents

def requests(w: World, week: int, open_slots: list[tuple]) -> list[tuple[str, tuple]]:
    """Which published shift slots (project, day, shift) each talent asks for this week, in their order of preference."""
    out = []
    for t in w.talents:
        r = rng(w.name, "requests", t.id, week)
        mine = [s for s in open_slots if s[0] in t.certified and (s[1], s[2]) in t.likes]
        r.shuffle(mine)
        want = int(round(t.hours_week / 4 * r.uniform(0.7, 1.2)))
        taken_days = set()
        for s in mine:
            if len(taken_days) >= want:
                break
            if (s[1], s[2]) in taken_days:
                continue
            taken_days.add((s[1], s[2]))
            out.append((t.id, s))
    order = rng(w.name, "request-order", week).permutation(len(out))
    return [out[int(i)] for i in order]


def shows(w: World, talent: str, week: int, day: int, shift: int) -> bool:
    t = next(x for x in w.talents if x.id == talent)
    return bool(rng(w.name, "show", talent, week, day, shift).random() >= t.noshow)


def accepts_callout(w: World, talent: str, week: int, day: int, iv: int) -> bool:
    return bool(rng(w.name, "callout", talent, week, day, iv).random() < w.cfg["talents"]["standby_accept"])


def talent(w: World, tid: str) -> Talent:
    return next(x for x in w.talents if x.id == tid)


# ---------------------------------------------------------------- service, the truth's version

def erlang_c_service(n: int, calls_: float, aht_s: float, interval_s: float, target_s: float = 20) -> tuple[float, float]:
    """(share answered within target_s, share abandoned) for n agents. Abandonment: callers wait at most ~60 s."""
    a = calls_ * aht_s / interval_s
    if calls_ <= 0:
        return 1.0, 0.0
    if n <= a:
        served = n / a if a > 0 else 1.0
        return 0.0, max(0.0, 1 - served * 1.05)
    s, term = 1.0, 1.0
    for k in range(1, n):
        term *= a / k
        s += term
    term *= a / n
    pc = term * n / (n - a) / (s + term * n / (n - a))
    sl = 1 - pc * math.exp(-(n - a) * target_s / aht_s)
    ab = pc * math.exp(-(n - a) * 60 / aht_s) * 0.5
    return float(sl), float(ab)


# ---------------------------------------------------------------- calls for quality review

PHRASES = {
    "greeting": ["Good morning, you are speaking with {n} from {b}, how can I help?",
                 "Hello and welcome to {b}, my name is {n}.", "Hi, {b} customer service, {n} speaking."],
    "identity": ["Before we continue, can you confirm your date of birth and postcode?",
                 "For security, please tell me your customer number and the first line of your address.",
                 "I need to verify you first: what is your contract number?"],
    "closing": ["To sum up, we changed your tariff today; is there anything else I can do?",
                "So I have booked the technician for Tuesday. Anything else for today?",
                "Let me summarise: the refund will arrive within five days. Have a good day."],
}
BREACH = ["I can promise you this will never happen again.", "I guarantee you will get a full refund, no problem.",
          "Don't worry, I will make sure your bill is cut in half.", "You will definitely get the discount, trust me.",
          "I personally assure you there will be no fees at all."]
FILLER = ["I understand, let me check that for you.", "One moment please while I look at your account.",
          "I see the issue in our system.", "That should be resolved now.", "Thank you for your patience.",
          "Could you repeat the last part?", "Your contract runs until next spring."]
HEDGE = ["I cannot promise a date, but I will escalate this today.", "I can't guarantee the outcome, the team decides.",
         "I won't make promises I can't keep; the refund needs approval."]
CUSTOMER = ["Yes, that's right.", "Okay.", "My bill is much higher this month.", "Can you promise me it won't happen again?",
            "I want a guarantee this time.", "Thanks.", "Hm, I see.", "When will it be fixed?"]


def transcripts(w: World, project: str, week: int, n: int) -> list[dict]:
    p = w.projects[project]
    pool = [t for t in w.talents if project in t.certified] or w.talents
    out = []
    for i in range(n):
        r = rng(w.name, "call", project, week, i)
        t = pool[int(r.integers(len(pool)))]
        truth = {}
        lines = []
        for g in p["guidelines"]:
            ok = bool(r.random() < t.quality)
            if g == "no_promise":
                truth[g] = ok
                continue
            truth[g] = ok
            if ok:
                lines.append((g, str(r.choice(PHRASES[g])).format(n="Alex", b=project.split("_")[0].title())))
        body = [str(r.choice(FILLER)) for _ in range(int(r.integers(3, 7)))]
        if "no_promise" in truth and not truth["no_promise"]:
            body.insert(int(r.integers(len(body) + 1)), str(r.choice(BREACH + w.cfg.get("breach_extra", []))))
        elif r.random() < 0.15:                                    # careful wording that names a promise it does not make
            body.insert(int(r.integers(len(body) + 1)), str(r.choice(HEDGE)))
        order = [x for g, x in lines if g == "greeting"] + [x for g, x in lines if g == "identity"] + body + \
                [x for g, x in lines if g == "closing"]
        text = []
        for x in order:
            text.append(f"agent: {x}")
            text.append(f"customer: {r.choice(CUSTOMER)}")
        out.append({"id": f"{project}-{week}-{i}", "project": project, "talent": t.id, "text": "\n".join(text),
                    "truth": truth})
    return out


# ---------------------------------------------------------------- what the talents' apps send

def session_events(w: World, tid: str, project: str, week: int, day: int, shift: int, load: float) -> tuple[list[dict], int]:
    """(events as the server receives them, true productive seconds). Productive = talking + after-call work."""
    b = w.cfg["billing"]
    p = w.projects[project]
    r = rng(w.name, "session", tid, week, day, shift)
    start_h, end_h = w.cfg["shifts"][shift]
    t0 = ((week * 7 + day) * 24 + start_h) * 3600
    end = ((week * 7 + day) * 24 + end_h) * 3600
    skew = int(r.integers(-b["clock_skew_s"], b["clock_skew_s"] + 1))
    ev, seq, now, productive = [], 0, t0 + int(r.integers(0, 300)), 0

    def emit(kind, ts, **kw):
        nonlocal seq
        seq += 1
        ev.append({"id": f"{tid}-{week}-{day}-{shift}-{seq}", "talent": tid, "project": project, "seq": seq,
                   "kind": kind, "ts": ts + skew, **kw})

    emit("login", now)
    crash = r.random() < b["crash_sessions"]
    crash_at = r.uniform(0.4, 0.9) * (end - t0) + t0 if crash else None
    last_hb = now
    while now < end - 120:
        if crash_at and now > crash_at:
            break
        if r.random() < b["pause_share"] / 3:
            d = int(r.integers(120, 600))
            emit("pause_start", now)
            now += d
            emit("pause_end", now)
            continue
        wait = int(r.exponential(p["aht_s"] * (1 / max(load, 0.2) - 0.8)))
        now += wait
        if now >= end - 120 or (crash_at and now > crash_at):
            break
        talk = int(r.gamma(4, p["aht_s"] / 4))
        acw = int(min(r.gamma(3, p["acw_s"] / 3), p["acw_s"] * 3))
        emit("call_start", now)
        emit("call_end", now + talk)
        emit("acw_end", now + talk + acw)
        productive += talk + acw
        now += talk + acw
        while last_hb + 300 < now:
            last_hb += 300
            emit("heartbeat", last_hb)
    if not crash:
        emit("logout", max(now, end - int(r.integers(0, 200))))
    # what the network does to it
    out = []
    for e in ev:
        out.append(e)
        if r.random() < b["duplicate_events"]:
            out.append(dict(e))
    late = [i for i in range(len(out)) if r.random() < b["late_events"]]
    for i in late:
        j = min(len(out) - 1, i + int(r.integers(1, 6)))
        out[i], out[j] = out[j], out[i]
    return out, productive

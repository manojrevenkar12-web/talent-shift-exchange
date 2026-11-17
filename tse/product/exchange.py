"""The shift exchange: plan the week from the forecast, publish slots, give requested shifts to talents by
reliability and fairness, book a little over the need where no-shows are expected, and call out standby talents when
a half hour runs hotter than planned."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from tse.product.forecast import Forecaster
from tse.product.service import agents_needed


@dataclass
class Profile:
    id: str
    certified: list[str]
    hours_week: int


@dataclass
class Plan:
    need: dict = field(default_factory=dict)       # (project, day, shift) -> headcount needed at the shift's peak
    by_interval: dict = field(default_factory=dict)   # (project, day, iv) -> agents needed


class Exchange:
    def __init__(self, cfg: dict, profiles: list[Profile], shifts: list[list[int]], intervals: list[tuple[int, int]]):
        self.cfg = cfg
        self.profiles = {p.id: p for p in profiles}
        self.shifts = shifts
        self.intervals = intervals
        a, b = cfg["allocation"]["reliability_prior"]
        self.shows = {p.id: [a, b] for p in profiles}            # Beta(shows, no-shows)
        self.granted_hours: dict[str, float] = {}
        self.offers = list(cfg["intraday"]["accept_prior"])      # Beta(accepted, declined) over all call-out offers
        self.requested_hours: dict[str, float] = {}

    # -------------------------------------------------------------- planning
    def shift_of(self, iv: int) -> int:
        h = self.intervals[iv][0]
        return next(k for k, (a, b) in enumerate(self.shifts) if a <= h < b)

    def plan(self, week: int, fc: Forecaster, projects: list[str], days: int = 7) -> Plan:
        plan = Plan()
        for p in projects:
            aht = self.cfg["projects"][p]["aht_s"]
            for d in range(days):
                for iv in range(len(self.intervals)):
                    plan.by_interval[(p, d, iv)] = agents_needed(fc.predict(p, week, d, iv), aht, self.cfg)
                for s in range(len(self.shifts)):
                    ivs = [iv for iv in range(len(self.intervals)) if self.shift_of(iv) == s]
                    plan.need[(p, d, s)] = max(plan.by_interval[(p, d, iv)] for iv in ivs)
        return plan

    def reliability(self, tid: str) -> float:
        a, b = self.shows[tid]
        return a / (a + b)

    def record_show(self, tid: str, showed: bool) -> None:
        self.shows[tid][0 if showed else 1] += 1

    # -------------------------------------------------------------- allocation
    def allocate(self, plan: Plan, requests: list[tuple[str, tuple]], shift_hours: float = 4.0) -> dict:
        """requests: (talent, (project, day, shift)) in arrival order. Returns slot -> list of talents."""
        al = self.cfg["allocation"]
        by_talent: dict[str, list] = {}
        for tid, slot in requests:
            by_talent.setdefault(tid, []).append(slot)
        for tid, slots in by_talent.items():
            self.requested_hours[tid] = self.requested_hours.get(tid, 0) + len(slots) * shift_hours

        def priority(tid: str) -> float:
            asked = self.requested_hours.get(tid, 1)
            unmet = 1 - self.granted_hours.get(tid, 0) / asked
            return self.reliability(tid) + al["fairness_weight"] * unmet

        valid = [(tid, slot) for tid, slot in requests if tid in self.profiles and slot[0] in self.profiles[tid].certified
                 and slot in plan.need]
        valid.sort(key=lambda x: -priority(x[0]))
        booked: dict[tuple, list] = {s: [] for s in plan.need}
        busy: dict[str, set] = {}
        week_shifts: dict[str, int] = {}

        def can(tid, slot):
            if (slot[1], slot[2]) in busy.get(tid, set()):
                return False
            return week_shifts.get(tid, 0) + 1 <= max(1, self.profiles[tid].hours_week // shift_hours)

        def take(tid, slot):
            booked[slot].append(tid)
            busy.setdefault(tid, set()).add((slot[1], slot[2]))
            week_shifts[tid] = week_shifts.get(tid, 0) + 1
            self.granted_hours[tid] = self.granted_hours.get(tid, 0) + shift_hours

        # first pass: fill the need; second pass: add bookings until the expected shows cover the need
        for tid, slot in valid:
            if len(booked[slot]) < plan.need[slot] and can(tid, slot):
                take(tid, slot)
        for tid, slot in valid:
            need = plan.need[slot]
            expected = sum(self.reliability(t) for t in booked[slot])
            if need and expected < need and len(booked[slot]) < need * (1 + al["overbook_cap"]) and can(tid, slot) \
                    and tid not in booked[slot]:
                take(tid, slot)
        return booked

    # -------------------------------------------------------------- intraday
    def record_offer(self, accepted: bool) -> None:
        self.offers[0 if accepted else 1] += 1

    def accept_rate(self) -> float:
        a, b = self.offers
        return a / (a + b)

    def callouts(self, project: str, iv: int, observed_prev: float, forecast_prev: float, forecast_now: float,
                 staffed: int, free: list[str]) -> tuple[list[str], dict]:
        """Who to offer a call-out shift to now, and why."""
        c = self.cfg["intraday"]
        ratio = observed_prev / forecast_prev if forecast_prev > 0 else 1.0
        expect = forecast_now * max(1.0, ratio if ratio >= c["surge_ratio"] else 1.0)
        need = agents_needed(expect, self.cfg["projects"][project]["aht_s"], self.cfg)
        short = need - staffed
        info = {"ratio": round(ratio, 2), "need": need, "staffed": staffed, "short": max(0, short)}
        if short <= 0:
            return [], info
        cands = sorted((t for t in free if project in self.profiles[t].certified), key=lambda t: -self.reliability(t))
        k = min(len(cands), c["max_offers_per_interval"], math.ceil(short / max(self.accept_rate(), 0.05)))
        return cands[:k], info

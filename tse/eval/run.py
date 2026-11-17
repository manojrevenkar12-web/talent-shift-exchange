"""One evaluation. Every design meets the same calls, the same talents asking for the same shifts, the same no-shows
and the same answers to call-out offers, because every draw is keyed by what it is about. Scored against the world."""
from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

from tse.eval.designs import QA, STAFFING, arrival_order_billing, fixed_plan, make
from tse.product import billing, qa
from tse.product.exchange import Profile
from tse.product.forecast import Forecaster
from tse.world import market as m
from tse.world.model import StandInModel

ROOT = Path(__file__).resolve().parents[2]


def settings() -> dict:
    return yaml.safe_load((ROOT / "config/exchange.yaml").read_text())


def staffing(w, cfg, design: str, fc: Forecaster, projects: list[str], log) -> dict:
    profiles = [Profile(t.id, t.certified, t.hours_week) for t in w.talents]
    ex = make(design, cfg, profiles, w.cfg["shifts"], w.intervals)
    H = w.cfg["history_weeks"]
    pause = w.cfg["billing"]["pause_share"]
    callout_on = design == "exchange"
    calls_tot = answered = abandoned = 0.0
    surge_calls = surge_answered = 0.0
    iv_ok = iv_n = 0
    logged_h, prod_min = defaultdict(float), defaultdict(float)
    asked_h, got_h = defaultdict(float), defaultdict(float)
    callout_offers = callout_taken = 0
    sessions = []                      # (talent, project, week, day, shift, occupancy) for billing
    booked_total = need_total = noshows = 0
    for week in range(H, H + w.weeks):
        plan = fixed_plan(ex, fc, week, projects) if design == "fixed_roster" else ex.plan(week, fc, projects)
        open_slots = [s for s, n in plan.need.items() if n > 0]
        reqs = m.requests(w, week, open_slots)
        for tid, _ in reqs:
            asked_h[tid] += 4
        booked = ex.allocate(plan, reqs)
        booked_total += sum(len(v) for v in booked.values())
        need_total += sum(plan.need.values())
        for slot, tids in booked.items():
            for t in tids:
                got_h[t] += 4
        for day in range(7):
            for s, (h0, h1) in enumerate(w.cfg["shifts"]):
                present, working = {}, set()
                for p in projects:
                    present[p] = []
                    for t in booked.get((p, day, s), []):
                        came = m.shows(w, t, week, day, s)
                        if design != "fixed_roster":
                            ex.record_show(t, came)
                        if came:
                            present[p].append(t)
                            working.add(t)
                        else:
                            noshows += 1
                callouts: dict[str, list[tuple[str, int]]] = {p: [] for p in projects}   # (talent, last interval)
                ivs = [iv for iv in range(len(w.intervals)) if ex.shift_of(iv) == s]
                occ_acc = defaultdict(list)
                ci = cfg["intraday"]["callout_intervals"]
                for iv in ivs:
                    for p in projects:
                        # a call-out offered at interval k works k+1 .. k+ci; offers end with the shift
                        callouts[p] = [(t, k) for t, k in callouts[p] if iv <= k + ci]
                        on = present[p] + [t for t, k in callouts[p] if k < iv]
                        if callout_on and iv > 0 and iv < ivs[-1]:
                            prev = iv - 1          # calls the phone system counted in the half hour just ended
                            free = [t.id for t in w.talents if t.id not in working and p in t.certified]
                            offers, _ = ex.callouts(p, iv, m.calls(w, p, week, day, prev),
                                                    fc.predict(p, week, day, prev), fc.predict(p, week, day, iv + 1),
                                                    len(present[p]) + len(callouts[p]), free)
                            callout_offers += len(offers)
                            for t in offers:
                                if m.accepts_callout(w, t, week, day, iv):
                                    callouts[p].append((t, iv))
                                    working.add(t)
                                    callout_taken += 1
                        c = m.calls(w, p, week, day, iv)
                        aht = w.projects[p]["aht_s"]
                        eff = int(round(len(on) * (1 - pause)))
                        sl, ab = m.erlang_c_service(eff, c, aht, 1800, cfg["service"]["answer_within_s"])
                        calls_tot += c
                        answered += sl * c
                        abandoned += ab * c
                        iv_n += 1
                        iv_ok += sl >= cfg["service"]["target_share"]
                        h = w.intervals[iv][0]
                        if any(x["project"] == p and x["week"] + H == week and x["day"] == day and
                               x["from_hour"] <= h < x["from_hour"] + x["hours"] for x in w.cfg["surges"]):
                            surge_calls += c
                            surge_answered += sl * c
                        busy = min(c * (1 - ab) * aht / 1800, eff)
                        per = busy / len(on) * 30 if on else 0
                        for t in on:
                            logged_h[t] += 0.5
                            prod_min[t] += per
                        if on:
                            occ_acc[p].append(busy / max(1, len(on)))
                for p in projects:
                    for t in present[p]:
                        sessions.append((t, p, week, day, s, float(np.mean(occ_acc[p])) if occ_acc[p] else 0.2))
        log(f"{design}: week {week - H + 1} done")
    rate = cfg["billing"]["eur_per_productive_min"]
    lh = sum(logged_h.values())
    eur = sum(prod_min.values()) * rate
    askers = [t for t in asked_h if asked_h[t] > 0]
    fill = [min(1.0, got_h[t] / asked_h[t]) for t in askers]
    return {
        "service_level": round(answered / calls_tot, 4) if calls_tot else None,
        "abandoned_calls": int(round(abandoned)),
        "calls": int(calls_tot),
        "intervals_on_target": round(iv_ok / iv_n, 4),
        "surge_service_level": round(surge_answered / surge_calls, 4) if surge_calls else None,
        "talent_eur_per_logged_hour": round(eur / lh, 2) if lh else 0,
        "talent_hours": round(lh),
        "talent_eur": round(eur),
        "talents_under_half_of_ask": round(float(np.mean([f < 0.5 for f in fill])), 4),
        "mean_fill": round(float(np.mean(fill)), 4),
        "booked_over_need": round(booked_total / need_total, 4) if need_total else None,
        "noshows": noshows,
        "callout_offers": callout_offers,
        "callouts_taken": callout_taken,
        "_sessions": sessions,
    }


def quality(w, cfg, projects: list[str], per_week: int) -> dict:
    H = w.cfg["history_weeks"]
    calls = [c for p in projects for wk in range(H, H + w.weeks) for c in m.transcripts(w, p, wk, per_week)]
    truth = {c["id"]: c["truth"] for c in calls}
    model = StandInModel(w, truth)
    out = {}
    checks = [(c, g) for c in calls for g in cfg["projects"][c["project"]]["guidelines"]]
    breaches = sum(not truth[c["id"]][g] for c, g in checks)
    clean = len(checks) - breaches
    promise = sum(g == "no_promise" and not truth[c["id"]][g] for c, g in checks)
    mins = cfg["qa"]["review_minutes"]
    for d in QA:
        found = false = reviewed_calls = 0
        p_found = 0
        if d == "manual_sample":
            for c in calls:
                if m.rng(w.name, "sample", c["id"]).random() < 0.05:
                    reviewed_calls += 1
                    found += sum(not v for v in c["truth"].values())
                    p_found += c["truth"].get("no_promise") is False
        else:
            review = set()
            for c in calls:
                g_list = cfg["projects"][c["project"]]["guidelines"]
                for f in qa.check(c, g_list, model, cfg):
                    t = truth[c["id"]][f.guideline]
                    if f.followed is None and d == "product":
                        review.add(c["id"])
                        found += not t                 # a person reads the call and gets it right
                        p_found += (not t) and f.guideline == "no_promise"
                        continue
                    said = f.followed if f.followed is not None else bool(f.confidence >= 0.5)
                    if d == "model_only" and f.followed is None:
                        said = model_says(model, c, f.guideline)
                    if not said and not t:
                        found += 1
                        p_found += f.guideline == "no_promise"
                    if not said and t:
                        false += 1
            reviewed_calls = len(review)
        out[d] = {"breach_recall": round(found / breaches, 4) if breaches else None,
                  "promise_breach_recall": round(p_found / promise, 4) if promise else None,
                  "false_flags": false, "false_flag_rate": round(false / clean, 4) if clean else 0,
                  "calls_read_by_people": reviewed_calls, "reviewer_hours": round(reviewed_calls * mins / 60, 1)}
    out["_calls"] = len(calls)
    out["_checks"] = len(checks)
    out["_breaches"] = breaches
    out["_promise_breaches"] = promise
    out["_all_by_people_hours"] = round(len(calls) * mins / 60, 1)
    for d in QA:
        out[d]["reviewer_share"] = round(out[d]["reviewer_hours"] / out["_all_by_people_hours"], 4)
    return out


def model_says(model, call, g) -> bool:
    return bool(model.judge(call["id"], qa.agent_lines(call["text"]), g)["followed"])


def pay(w, cfg, sessions) -> dict:
    rate = cfg["billing"]["eur_per_productive_min"]
    events, true_s = [], defaultdict(int)
    for t, p, week, day, s, occ in sessions:
        ev, prod = m.session_events(w, t, p, week, day, s, occ)
        events.extend(ev)
        true_s[t] += prod
    truth = {t: int(round(v / 60 * rate * 100)) for t, v in true_s.items()}
    st = billing.statements(events, "eval", cfg)
    designs = {"arrival_order": arrival_order_billing(events, rate),
               "product": {t: s.cents for t, s in st.items()}}
    out = {}
    for d, paid in designs.items():
        over = sum(max(0, paid.get(t, 0) - truth[t]) for t in truth)
        under = sum(max(0, truth[t] - paid.get(t, 0)) for t in truth)
        wrong = sum(abs(paid.get(t, 0) - truth[t]) > 1 for t in truth)      # one cent of rounding allowed
        out[d] = {"overpaid_cents": over, "underpaid_cents": under, "talents_paid_wrong": wrong,
                  "error_share": round((over + under) / max(1, sum(truth.values())), 5)}
    out["_events"] = len(events)
    out["_duplicates"] = len(events) - len({e["id"] for e in events})
    out["_sessions"] = len(sessions)
    out["_talents"] = len(truth)
    out["_true_cents"] = sum(truth.values())
    return out


def race(talents: int = 200, seats: int = 40, workers: int = 32) -> dict:
    """Many talents claim one popular shift at the same moment, through the store the API uses."""
    import tempfile
    from concurrent.futures import ThreadPoolExecutor

    from tse.product import db as store
    with tempfile.TemporaryDirectory() as tmp:
        db = store.connect(f"sqlite:///{tmp}/race.db")
        with db() as s:
            s.add(store.Slot(id="telco_de|9|0|0", project="telco_de", week=9, day=0, shift=0, seats=seats))
            for i in range(talents):
                s.add(store.Talent(id=f"R{i}", certified=["telco_de"], hours_week=20))
            s.commit()

        def go(i):
            try:
                return store.claim(db, "telco_de|9|0|0", f"R{i}")
            except store.Full:
                return None
        order = list(range(talents)) + list(range(0, talents, 4))      # every fourth talent taps twice
        with ThreadPoolExecutor(workers) as ex:
            res = list(ex.map(go, order))
        from sqlalchemy import func, select
        with db() as s:
            rows = s.execute(select(store.Seat.seat_no, func.count()).group_by(store.Seat.seat_no)).all()
            holders = s.execute(select(store.Seat.talent_id, func.count()).group_by(store.Seat.talent_id)).all()
        db.kw["bind"].dispose()
    return {"claims": len(order), "seats": seats, "seats_taken": len(rows),
            "double_bookings": sum(n - 1 for _, n in rows if n > 1) + sum(n - 1 for _, n in holders if n > 1),
            "refused_full": sum(r is None for r in res)}


def evaluate(world_file: str = "config/world.yaml", quick: bool = False, log=print) -> dict:
    cfg = settings()
    w = m.load(ROOT / world_file, quick)
    projects = list(w.projects)
    t0 = time.perf_counter()
    fc = Forecaster(cfg)
    H = w.cfg["history_weeks"]
    for week in range(H + w.weeks):           # the forecaster sees each week only once it is over
        for p in projects:
            for d in range(7):
                for iv in range(len(w.intervals)):
                    fc.observe(p, week, d, iv, m.calls(w, p, week, d, iv))
    # predictions only ever read weeks before the one asked about (Forecaster.predict filters k < week)
    staff = {d: staffing(w, cfg, d, fc, projects, log) for d in STAFFING}
    log(f"staffing done ({time.perf_counter() - t0:.0f} s)")
    billing_rep = pay(w, cfg, staff["exchange"].pop("_sessions"))
    for d in STAFFING:
        staff[d].pop("_sessions", None)
    log(f"billing done ({time.perf_counter() - t0:.0f} s)")
    qrep = quality(w, cfg, projects, 60 if quick else 250)
    log(f"quality done ({time.perf_counter() - t0:.0f} s)")
    api = race()
    log(f"claim race done ({time.perf_counter() - t0:.0f} s)")
    return {"world": w.name, "weeks": w.weeks, "talents": len(w.talents), "projects": projects,
            "staffing": staff, "billing": billing_rep, "quality": qrep, "api": api}


def write_report(rep: dict, name: str) -> Path:
    import json
    out = ROOT / "reports" / f"{name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, sort_keys=False) + "\n")
    return out

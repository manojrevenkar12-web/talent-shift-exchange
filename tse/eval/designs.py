"""The designs compared. Staffing: a fixed roster planned on the average day (what many contact centres still do),
the exchange without intraday call-outs, and the full exchange. Billing: a ledger that reads events as they arrive,
and the product's ledger. Quality: a person samples calls, the model alone decides, and the product."""
from __future__ import annotations

import copy
from collections import defaultdict

from tse.product.exchange import Exchange, Plan
from tse.product.service import agents_needed

STAFFING = ["fixed_roster", "exchange_no_callouts", "exchange"]
QA = ["manual_sample", "model_only", "product"]
BILLING = ["arrival_order", "product"]


def make(design: str, cfg: dict, profiles, shifts, intervals) -> Exchange:
    c = copy.deepcopy(cfg)
    if design == "fixed_roster":
        c["allocation"]["overbook_cap"] = 0.0
        c["allocation"]["fairness_weight"] = 0.0
    return Exchange(c, profiles, shifts, intervals)


def fixed_plan(ex: Exchange, fc, week: int, projects: list[str], days: int = 7) -> Plan:
    """One headcount per project and shift, from the average day of recent weeks, the same on every day."""
    plan = Plan()
    n_iv = len(ex.intervals)
    for p in projects:
        aht = ex.cfg["projects"][p]["aht_s"]
        avg = {iv: sum(fc.predict(p, week, d, iv) for d in range(days)) / days for iv in range(n_iv)}
        for s in range(len(ex.shifts)):
            need = max(agents_needed(avg[iv], aht, ex.cfg) for iv in range(n_iv) if ex.shift_of(iv) == s)
            for d in range(days):
                plan.need[(p, d, s)] = need
    return plan


def arrival_order_billing(events: list[dict], rate: float) -> dict[str, int]:
    """Pay talk plus after-call work from the events in the order they arrived, without removing repeats."""
    secs, start = defaultdict(int), {}
    for e in events:
        k = e["id"].rsplit("-", 1)[0]
        if e["kind"] == "call_start":
            start[k] = e["ts"]
        elif e["kind"] == "acw_end" and k in start:
            secs[e["talent"]] += max(0, e["ts"] - start.pop(k))
    return {t: int(round(s / 60 * rate * 100)) for t, s in secs.items()}

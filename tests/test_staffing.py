from tse.eval.run import settings
from tse.product.exchange import Exchange, Plan, Profile
from tse.product.forecast import Forecaster
from tse.product.service import agents_needed, service_level

CFG = settings()
SHIFTS = [[8, 12], [12, 16], [16, 20]]
IVS = [(h, m) for h in range(8, 20) for m in (0, 30)]


def test_more_calls_never_need_fewer_talents():
    needs = [agents_needed(c, 330, CFG) for c in range(0, 120, 5)]
    assert needs == sorted(needs)
    n = agents_needed(70, 330, CFG)
    assert service_level(int(n * (1 - CFG["service"]["shrinkage"])), 70, 330, 1800, 20) >= 0.8


def test_forecast_reads_only_weeks_before_the_one_asked():
    fc = Forecaster(CFG)
    for wk, c in enumerate([50, 52, 54, 500]):
        fc.observe("telco_de", wk, 0, 4, c)
    assert fc.predict("telco_de", 3, 0, 4) < 60          # week 3's 500 calls are not seen when forecasting week 3


def ex(profiles, **alloc):
    cfg = {**CFG, "allocation": {**CFG["allocation"], **alloc}}
    return Exchange(cfg, profiles, SHIFTS, IVS)


def test_allocation_keeps_certification_one_place_at_a_time_and_hours():
    ps = [Profile("A", ["telco_de"], 8), Profile("B", ["shop_en"], 30)]
    e = ex(ps)
    plan = Plan(need={("telco_de", 0, 0): 2, ("shop_en", 0, 0): 2, ("telco_de", 1, 0): 2, ("telco_de", 2, 0): 2})
    reqs = [("A", ("telco_de", 0, 0)), ("A", ("telco_de", 1, 0)), ("A", ("telco_de", 2, 0)),
            ("B", ("telco_de", 0, 0)), ("B", ("shop_en", 0, 0))]
    booked = e.allocate(plan, reqs)
    assert "B" not in booked[("telco_de", 0, 0)]                  # not certified
    assert sum("A" in v for v in booked.values()) == 2             # 8 hours a week is two shifts
    assert booked[("shop_en", 0, 0)] == ["B"]


def test_unreliable_talents_are_booked_over_the_need_within_the_cap():
    ps = [Profile(f"T{i}", ["telco_de"], 20) for i in range(10)]
    e = ex(ps, overbook_cap=0.25)
    for i in range(10):
        for _ in range(8):
            e.record_show(f"T{i}", i % 2 == 0)                      # half of them miss half their shifts
    plan = Plan(need={("telco_de", 0, 0): 4})
    booked = e.allocate(plan, [(f"T{i}", ("telco_de", 0, 0)) for i in range(10)])
    assert 4 < len(booked[("telco_de", 0, 0)]) <= 5


def test_fairness_lifts_talents_who_got_little():
    ps = [Profile("A", ["telco_de"], 30), Profile("B", ["telco_de"], 30)]
    e = ex(ps, fairness_weight=1.0)
    e.requested_hours = {"A": 40, "B": 40}
    e.granted_hours = {"A": 40, "B": 0}
    booked = e.allocate(Plan(need={("telco_de", 0, 0): 1}), [("A", ("telco_de", 0, 0)), ("B", ("telco_de", 0, 0))])
    assert booked[("telco_de", 0, 0)][0] == "B"                     # A may still come as the overbooked extra


def test_callouts_only_in_a_surge_or_a_gap_and_only_to_certified_free_talents():
    ps = [Profile("A", ["telco_de"], 20), Profile("B", ["shop_en"], 20), Profile("C", ["telco_de"], 20)]
    e = ex(ps)
    need = agents_needed(60, 330, CFG)
    offers, info = e.callouts("telco_de", 5, observed_prev=60, forecast_prev=60, forecast_now=60, staffed=need,
                              free=["A", "B", "C"])
    assert offers == [] and info["short"] == 0
    offers, info = e.callouts("telco_de", 5, observed_prev=110, forecast_prev=60, forecast_now=60, staffed=need,
                              free=["A", "B", "C"])
    assert info["short"] > 0 and set(offers) == {"A", "C"}

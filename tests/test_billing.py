from tse.eval.designs import arrival_order_billing
from tse.eval.run import settings
from tse.product.billing import statements
from tse.world import market as m

CFG = settings()


def ev(i, kind, ts, seq):
    return {"id": f"T1-3-0-0-{seq}", "talent": "T1", "project": "telco_de", "seq": seq, "kind": kind, "ts": ts}


def test_repeats_and_late_events_are_paid_once():
    base = [ev(0, "login", 0, 1), ev(0, "call_start", 100, 2), ev(0, "call_end", 400, 3), ev(0, "acw_end", 460, 4),
            ev(0, "call_start", 1000, 5), ev(0, "call_end", 1300, 6), ev(0, "acw_end", 1360, 7)]
    messy = [base[0], base[2], base[1], base[1], base[4], base[3], base[5], base[6], base[6]]
    # above: the next call starts before the last one's after-call work arrives
    assert statements(messy, "p", CFG)["T1"].productive_s == statements(base, "p", CFG)["T1"].productive_s == 720
    assert arrival_order_billing(messy, 0.24)["T1"] != statements(base, "p", CFG)["T1"].cents


def test_after_call_work_is_paid_up_to_the_contract_cap_and_an_open_call_is_not_paid():
    long_acw = [ev(0, "call_start", 0, 1), ev(0, "call_end", 300, 2), ev(0, "acw_end", 2000, 3),
                ev(0, "call_start", 3000, 4)]
    st = statements(long_acw, "p", CFG)["T1"]
    assert st.productive_s == 300 + CFG["projects"]["telco_de"]["acw_cap_s"]
    assert st.open_calls == 1
    assert isinstance(st.cents, int)


def test_the_world_messes_up_events_and_the_ledger_still_pays_exactly():
    w = m.load("config/world.yaml", quick=True)
    t = w.talents[0]
    total, events = 0, []
    for d in range(7):
        e, prod = m.session_events(w, t.id, "telco_de", 3, d, 0, 0.8)
        events += e
        total += prod
    assert len(events) > len({x["id"] for x in events})            # there were repeats
    assert statements(events, "p", CFG)[t.id].productive_s == total

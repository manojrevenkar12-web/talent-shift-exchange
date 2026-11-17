from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from tse.product import db as store
from tse.product.api import create_app


def client(tmp_path):
    return TestClient(create_app(f"sqlite:///{tmp_path}/x.db"))


def test_many_talents_racing_for_few_seats_fill_each_seat_once(tmp_path):
    db = store.connect(f"sqlite:///{tmp_path}/race.db")
    with db() as s:
        s.add(store.Slot(id="s", project="telco_de", week=3, day=0, shift=0, seats=12))
        s.add_all(store.Talent(id=f"T{i}", certified=["telco_de"], hours_week=20) for i in range(80))
        s.commit()

    def go(i):
        try:
            return store.claim(db, "s", f"T{i % 80}")
        except store.Full:
            return None
    with ThreadPoolExecutor(24) as ex:
        res = list(ex.map(go, range(120)))
    won = {}
    for i, r in enumerate(res):
        if r is not None:
            won.setdefault(f"T{i % 80}", set()).add(r)
    assert store.seats_taken(db, "s") == 12
    assert all(len(v) == 1 for v in won.values())                       # tapping twice is one seat
    assert sorted(x for v in won.values() for x in v) == list(range(12))


def test_claim_rules_events_and_statements(tmp_path):
    c = client(tmp_path)
    c.post("/talents", json={"id": "A", "certified": ["telco_de"], "hours_week": 20})
    c.post("/talents", json={"id": "B", "certified": ["shop_en"], "hours_week": 20})
    sid = c.post("/slots", json=[{"project": "telco_de", "week": 3, "day": 0, "shift": 0, "seats": 1},
                                 {"project": "telco_de", "week": 3, "day": 0, "shift": 1, "seats": 1}]).json()["slots"]
    assert c.post(f"/slots/{sid[0]}/claim", params={"talent": "B"}).status_code == 403
    assert c.post(f"/slots/{sid[0]}/claim", params={"talent": "A"}).json()["seat"] == 0
    assert c.post(f"/slots/{sid[0]}/claim", params={"talent": "A"}).status_code == 201     # same claim again
    assert [x["id"] for x in c.get("/slots", params={"week": 3, "talent": "A"}).json()] == [sid[1]]
    evs = [{"id": f"A-3-0-0-{k}", "talent": "A", "project": "telco_de", "seq": k, "kind": kind, "ts": ts}
           for k, kind, ts in [(1, "call_start", 0), (2, "call_end", 300), (3, "acw_end", 360)]]
    assert c.post("/events", json=evs + evs[:1]).json() == {"stored": 3, "repeats": 1}
    first = c.post("/statements/2026-W47", params={"talent": "A"}).json()
    assert first["cents"] == round(360 / 60 * 0.24 * 100) and first["issued"]
    c.post("/events", json=[{**evs[0], "id": "A-3-0-0-9", "seq": 9}])
    again = c.post("/statements/2026-W47", params={"talent": "A"}).json()
    assert again["cents"] == first["cents"] and not again["issued"]            # issued once, then only read
    assert c.post("/slots", json=[{"project": "nope", "week": 3, "day": 0, "shift": 0, "seats": 1}]).status_code == 422

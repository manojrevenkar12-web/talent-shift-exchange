import os
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from tse.product import db as store
from tse.product.api import create_app


def url(tmp_path, name: str) -> str:
    """SQLite by default; CI also runs these against Postgres (TSE_TEST_DB), starting from empty tables."""
    pg = os.environ.get("TSE_TEST_DB")
    if not pg:
        return f"sqlite:///{tmp_path}/{name}.db"
    eng = create_engine(pg)
    store.Base.metadata.drop_all(eng)
    eng.dispose()
    return pg


def client(tmp_path):
    return TestClient(create_app(url(tmp_path, "x")))


def test_many_talents_racing_for_few_seats_fill_each_seat_once(tmp_path):
    db = store.connect(url(tmp_path, "race"))
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
    first = c.post("/statements/3", params={"talent": "A"}).json()
    assert first["cents"] == round(360 / 60 * 0.24 * 100) and first["added"]["version"] == 1
    assert c.post("/statements/3", params={"talent": "A"}).json()["added"] is None          # nothing new, nothing added
    late = [{"id": f"A-3-0-0-{k}", "talent": "A", "project": "telco_de", "seq": k, "kind": kind, "ts": ts}
            for k, kind, ts in [(4, "call_start", 1000), (5, "call_end", 1120), (6, "acw_end", 1180)]]
    c.post("/events", json=late)
    adj = c.post("/statements/3", params={"talent": "A"}).json()
    assert adj["added"] == {"version": 2, "cents": round(180 / 60 * 0.24 * 100)}            # late work, added on top
    assert c.post("/statements/4", params={"talent": "A"}).status_code == 404               # week 4 pays nothing of week 3
    assert c.post("/slots", json=[{"project": "nope", "week": 3, "day": 0, "shift": 0, "seats": 1}]).status_code == 422


def test_metrics_count_what_happened(tmp_path):
    c = client(tmp_path)
    c.post("/talents", json={"id": "A", "certified": ["telco_de"], "hours_week": 20})
    sid = c.post("/slots", json=[{"project": "telco_de", "week": 3, "day": 0, "shift": 0, "seats": 1}]).json()["slots"][0]
    c.post(f"/slots/{sid}/claim", params={"talent": "A"})
    ev = {"id": "A-3-0-0-1", "talent": "A", "project": "telco_de", "seq": 1, "kind": "call_start", "ts": 0}
    c.post("/events", json=[ev, ev])
    text = c.get("/metrics").text
    assert 'tse_claims_total{outcome="seated"} 1.0' in text
    assert 'tse_events_total{outcome="repeat"} 1.0' in text
    assert 'tse_request_seconds_count{route="/slots/{slot_id}/claim",status="201"} 1.0' in text

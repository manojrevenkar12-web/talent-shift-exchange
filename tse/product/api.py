"""The exchange's HTTP API: publish a week's slots, let talents claim them, take the apps' events and issue pay
statements. Claims and events are safe to repeat; an issued statement row is never changed, late work adds a row."""
from __future__ import annotations

import os
import time
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from pydantic import BaseModel
from sqlalchemy import select

from tse.product import billing
from tse.product import db as store

ROOT = Path(__file__).resolve().parents[2]


class SlotIn(BaseModel):
    project: str
    week: int
    day: int
    shift: int
    seats: int


class TalentIn(BaseModel):
    id: str
    certified: list[str]
    hours_week: int


class EventIn(BaseModel):
    id: str
    talent: str
    project: str
    seq: int
    kind: str
    ts: int


def create_app(url: str | None = None, cfg: dict | None = None) -> FastAPI:
    cfg = cfg or yaml.safe_load((ROOT / "config/exchange.yaml").read_text())
    db = store.connect(url or os.environ.get("TSE_DB", "sqlite://"))
    app = FastAPI(title="talent-shift-exchange")
    app.state.db = db
    reg = CollectorRegistry()           # one registry per app, so tests and workers do not share counters
    claims = Counter("tse_claims", "Shift claims by outcome", ["outcome"], registry=reg)
    events_c = Counter("tse_events", "App events received", ["outcome"], registry=reg)
    statements_c = Counter("tse_statement_rows", "Statement rows written", ["kind"], registry=reg)
    latency = Histogram("tse_request_seconds", "Request latency", ["route", "status"], registry=reg)

    @app.middleware("http")
    async def timed(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        latency.labels(getattr(route, "path", "unmatched"), str(response.status_code)).observe(time.perf_counter() - t0)
        return response

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(reg), media_type=CONTENT_TYPE_LATEST)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/talents", status_code=201)
    def add_talent(t: TalentIn):
        with db() as s:
            s.merge(store.Talent(id=t.id, certified=t.certified, hours_week=t.hours_week))
            s.commit()
        return {"id": t.id}

    @app.post("/slots", status_code=201)
    def publish(slots: list[SlotIn]):
        ids = []
        with db() as s:
            for x in slots:
                if x.project not in cfg["projects"]:
                    raise HTTPException(422, f"unknown project {x.project}")
                sid = f"{x.project}|{x.week}|{x.day}|{x.shift}"
                s.merge(store.Slot(id=sid, project=x.project, week=x.week, day=x.day, shift=x.shift, seats=x.seats))
                ids.append(sid)
            s.commit()
        return {"slots": ids}

    @app.get("/slots")
    def open_slots(week: int, talent: str | None = None):
        with db() as s:
            rows = s.scalars(select(store.Slot).where(store.Slot.week == week)).all()
            t = s.get(store.Talent, talent) if talent else None
        out = []
        for r in rows:
            if t is not None and r.project not in t.certified:
                continue
            left = r.seats - store.seats_taken(db, r.id)
            if left > 0:
                out.append({"id": r.id, "project": r.project, "day": r.day, "shift": r.shift, "free": left})
        return out

    @app.post("/slots/{slot_id}/claim", status_code=201)
    def claim(slot_id: str, talent: str):
        try:
            seat = store.claim(db, slot_id, talent)
        except store.Full:
            claims.labels("full").inc()
            raise HTTPException(409, "this shift is full")
        except store.NotAllowed as e:
            claims.labels("refused").inc()
            raise HTTPException(403, str(e))
        claims.labels("seated").inc()
        return {"slot": slot_id, "seat": seat}

    @app.post("/events")
    def events(batch: list[EventIn]):
        stored, repeats = store.store_events(db, [e.model_dump() for e in batch])
        events_c.labels("stored").inc(stored)
        events_c.labels("repeat").inc(repeats)
        return {"stored": stored, "repeats": repeats}

    @app.post("/statements/{week}")
    def statements(week: int, talent: str):
        """Pay for the work done in a week. Issued rows are never changed: events that arrive after the statement
        add an adjustment row with the difference, and asking again with nothing new adds nothing."""
        with db() as s:
            rows = s.scalars(select(store.StatementRow).where(store.StatementRow.talent == talent,
                                                              store.StatementRow.period == str(week))).all()
            evs = [{"id": e.id, "talent": e.talent, "project": e.project, "seq": e.seq, "kind": e.kind, "ts": e.ts}
                   for e in s.scalars(select(store.Event).where(store.Event.talent == talent))]
            evs = [e for e in evs if billing.session_week(e) == week]
            st = billing.statements(evs, str(week), cfg).get(talent)
            if st is None:
                raise HTTPException(404, "no work recorded for this talent in this week")
            paid_c, paid_s = sum(r.cents for r in rows), sum(r.productive_s for r in rows)
            added = None
            if st.cents != paid_c or not rows:
                added = store.StatementRow(talent=talent, period=str(week), version=len(rows) + 1,
                                           productive_s=st.productive_s - paid_s, cents=st.cents - paid_c)
                s.add(added)
                s.commit()
                statements_c.labels("statement" if added.version == 1 else "adjustment").inc()
        return {"talent": talent, "week": week, "productive_s": st.productive_s, "cents": st.cents,
                "added": None if added is None else {"version": added.version, "cents": added.cents}}

    return app


app = create_app() if os.environ.get("TSE_SERVE") else None

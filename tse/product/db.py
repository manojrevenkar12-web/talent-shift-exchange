"""The exchange's store. Correctness under load comes from constraints, not from locks in Python: a seat is a row
with a unique (slot, seat number), a talent can hold one seat per slot and one shift at a time, and an app event is
stored once by its id. The same code runs on SQLite in tests and on Postgres in production."""
from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint, create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Talent(Base):
    __tablename__ = "talents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    certified: Mapped[list] = mapped_column(JSON)
    hours_week: Mapped[int] = mapped_column(Integer)


class Slot(Base):
    __tablename__ = "slots"
    id: Mapped[str] = mapped_column(String, primary_key=True)          # project|week|day|shift
    project: Mapped[str] = mapped_column(String)
    week: Mapped[int] = mapped_column(Integer)
    day: Mapped[int] = mapped_column(Integer)
    shift: Mapped[int] = mapped_column(Integer)
    seats: Mapped[int] = mapped_column(Integer)                         # need plus the overbooking the plan allows


class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = (UniqueConstraint("slot_id", "seat_no"), UniqueConstraint("slot_id", "talent_id"),
                      UniqueConstraint("talent_id", "week", "day", "shift"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_id: Mapped[str] = mapped_column(ForeignKey("slots.id"))
    seat_no: Mapped[int] = mapped_column(Integer)
    talent_id: Mapped[str] = mapped_column(ForeignKey("talents.id"))
    week: Mapped[int] = mapped_column(Integer)
    day: Mapped[int] = mapped_column(Integer)
    shift: Mapped[int] = mapped_column(Integer)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String, primary_key=True)          # the app's own id: a resend is the same row
    talent: Mapped[str] = mapped_column(String, index=True)
    project: Mapped[str] = mapped_column(String)
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String)
    ts: Mapped[int] = mapped_column(Integer)


class StatementRow(Base):
    __tablename__ = "statements"
    __table_args__ = (UniqueConstraint("talent", "period", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    talent: Mapped[str] = mapped_column(String)
    period: Mapped[str] = mapped_column(String)          # the week the work was done in
    version: Mapped[int] = mapped_column(Integer)        # 1 is the statement, 2.. are adjustments for late events
    productive_s: Mapped[int] = mapped_column(Integer)   # added in this row
    cents: Mapped[int] = mapped_column(Integer)          # added in this row; issued rows are never changed


def connect(url: str = "sqlite://") -> sessionmaker:
    kw = {}
    if url.startswith("sqlite"):
        kw = {"connect_args": {"check_same_thread": False, "timeout": 30}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            from sqlalchemy.pool import StaticPool
            kw["poolclass"] = StaticPool
    elif url.startswith("postgresql"):
        kw = {"pool_size": 40, "max_overflow": 0}       # enough connections for a burst of claims
    engine = create_engine(url, **kw)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


class Full(Exception):
    pass


class NotAllowed(Exception):
    pass


def claim(db: sessionmaker, slot_id: str, talent_id: str) -> int:
    """Give the talent the lowest free seat. Two talents racing for the last seat: the database lets one row in."""
    with db() as s:
        slot = s.get(Slot, slot_id)
        t = s.get(Talent, talent_id)
        if slot is None or t is None:
            raise NotAllowed("unknown slot or talent")
        if slot.project not in t.certified:
            raise NotAllowed("not certified for this project")
        mine = s.scalar(select(Seat.seat_no).where(Seat.slot_id == slot_id, Seat.talent_id == talent_id))
        if mine is not None:
            return mine                                    # claiming twice is the same claim
    for _ in range(slot.seats * 4):
        with db() as s:
            taken = set(s.scalars(select(Seat.seat_no).where(Seat.slot_id == slot_id)))
            free = [n for n in range(slot.seats) if n not in taken]
            if not free:
                raise Full(slot_id)
            s.add(Seat(slot_id=slot_id, seat_no=free[0], talent_id=talent_id, week=slot.week, day=slot.day,
                       shift=slot.shift))
            try:
                s.commit()
                return free[0]
            except IntegrityError:
                s.rollback()
                mine = s.scalar(select(Seat.seat_no).where(Seat.slot_id == slot_id, Seat.talent_id == talent_id))
                if mine is not None:
                    return mine
                busy = s.scalar(select(Seat.id).where(Seat.talent_id == talent_id, Seat.week == slot.week,
                                                      Seat.day == slot.day, Seat.shift == slot.shift))
                if busy is not None:
                    raise NotAllowed("already working another slot at this time")
    raise Full(slot_id)


def store_events(db: sessionmaker, events: list[dict]) -> tuple[int, int]:
    """(stored, repeats). Each event is its own insert so one repeat does not drop the rest of the batch."""
    stored = repeats = 0
    with db() as s:
        for e in events:
            sp = s.begin_nested()
            try:
                s.add(Event(**{k: e[k] for k in ("id", "talent", "project", "seq", "kind", "ts")}))
                s.flush()
                stored += 1
            except IntegrityError:
                sp.rollback()
                repeats += 1
        s.commit()
    return stored, repeats


def seats_taken(db: sessionmaker, slot_id: str) -> int:
    with db() as s:
        return s.scalar(select(func.count()).select_from(Seat).where(Seat.slot_id == slot_id)) or 0


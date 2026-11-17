"""README from the reports: every number in it comes from reports/dev.json or reports/heldout.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAFF = {"fixed_roster": "Fixed roster", "exchange_no_callouts": "Exchange, no call-outs", "exchange": "**Exchange**"}
QA = {"manual_sample": "People listen to 5% of calls", "model_only": "The model decides alone", "product": "**Product**"}


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.1f}%"


def eur(c) -> str:
    return f"€{c / 100:,.0f}"


def show(x) -> str:
    v = x["value"]
    if isinstance(v, float):
        return f"{v:.4g}"
    return f"{v:,}" if isinstance(v, int) else str(v)


def render() -> str:
    dev = json.loads((ROOT / "reports/dev.json").read_text())
    hp = ROOT / "reports/heldout.json"
    held = json.loads(hp.read_text()) if hp.exists() else None
    s, h = dev["staffing"], (held["staffing"] if held else None)
    rows = []
    for k, d in s.items():
        hd = h[k] if h else None
        rows.append(f"| {STAFF[k]} | {pct(d['service_level'])} | {pct(d['intervals_on_target'])} | "
                    f"{d['abandoned_calls']:,} | {pct(d['surge_service_level'])} | €{d['talent_eur_per_logged_hour']:.2f} | "
                    f"{pct(d['talents_under_half_of_ask'])} | "
                    + (f"{pct(hd['service_level'])}, {hd['abandoned_calls']:,} lost, surge {pct(hd['surge_service_level'])} |"
                       if hd else "– |"))
    q, hq = dev["quality"], (held["quality"] if held else None)
    qrows = []
    for k, d in ((k, q[k]) for k in QA):
        hd = hq[k] if hq else None
        qrows.append(f"| {QA[k]} | {pct(d['promise_breach_recall'])} | {pct(d['breach_recall'])} | {d['false_flags']} | "
                     f"{d['reviewer_hours']} h | "
                     + (f"{pct(hd['promise_breach_recall'])}, {hd['false_flags']} false, {hd['reviewer_hours']} h |" if hd else "– |"))
    b, hb = dev["billing"], (held["billing"] if held else None)
    brows = []
    for k, name in (("arrival_order", "Events in the order they arrive"), ("product", "**Ledger by sequence number**")):
        d = b[k]
        hd = hb[k] if hb else None
        brows.append(f"| {name} | {eur(d['overpaid_cents'])} | {eur(d['underpaid_cents'])} | {d['talents_paid_wrong']} of "
                     f"{b['_talents']} | " + (f"{pct(hd['error_share'])} of pay wrong, {hd['talents_paid_wrong']} talents |"
                                              if hd else "– |"))
    gate = []
    for i, g in enumerate(dev["gate"]):
        hg = held["gate"][i] if held else None
        gate.append(f"| {g['name']} | {show(g)} {'✅' if g['pass'] else '❌'} | "
                    + (f"{show(hg)} {'✅' if hg['pass'] else '❌'} |" if hg else "– |"))
    passed = sum(g["pass"] for g in dev["gate"])
    hpassed = sum(g["pass"] for g in held["gate"]) if held else 0
    ex, fx = s["exchange"], s["fixed_roster"]
    a = dev["api"]
    return f"""# talent-shift-exchange

A shift exchange for a freelance contact-centre marketplace. Client projects need people on the phone in every half
hour; freelance talents pick the shifts they want from home; the platform has to make both work. It does five things:

- **plans** each half hour from a forecast of calls and Erlang C, per project, language and weekday;
- **books** the shifts talents ask for by how reliably they show up and how much of their ask they have had, and books
  a little over the need where no-shows are expected;
- **calls out** free, certified talents when a half hour runs hotter than planned or people do not log in;
- **pays** talents per productive minute from the events their apps send, which arrive twice, late and out of order;
- **checks calls** against each client's guidelines: rules for fixed phrases, a model for promises an agent may not
  make, and a person for every call the model is not sure about.

A FastAPI service with SQLAlchemy carries the claims and the ledger, on Postgres in production and SQLite in tests;
CI runs the claim race on both. A seat is a database row, so two talents tapping the last seat at once cannot both get
it. The API exports Prometheus metrics (claims by outcome, repeated events, statement rows, latency by route), and
`docker compose up` starts it with Postgres, Prometheus and a Grafana dashboard. Everything is measured against a simulated marketplace
({dev['talents']} talents, 4 client projects in German, English and French, {dev['weeks']} weeks) and a held-out
marketplace that was run once.

![dashboard](docs/dashboard.png)

## Staffing

Dev world, {s['exchange']['calls']:,} calls. Every design meets the same calls, the same talents asking for the same
shifts, and the same no-shows, because every draw is keyed by what it is about. The held-out world H1 was run once.

| design | answered in 20 s | half hours on 80/20 | abandoned calls | answered in surges | talent € per logged hour | talents under half their ask | held-out H1 |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

- **Fixed roster:** one headcount per project and shift, planned on the average day and used every day, first come
  first served. Many contact centres still plan this way. Mondays and peaks are short, and quiet weekends are overstaffed.
- **Exchange, no call-outs:** the weekday- and half-hour-aware plan, reliability-aware overbooking and fairness, but
  nothing changes once the week starts.
- **Exchange:** the plan plus intraday call-outs. Over {dev['weeks']} weeks it sent {ex['callout_offers']:,} offers and
  {ex['callouts_taken']:,} were taken.

Talents are paid per productive minute, so staffing up costs them occupancy: the exchange answers
{100 * (ex['service_level'] - fx['service_level']):.1f} points more of the calls in 20 s than the fixed roster, and talents earn
€{ex['talent_eur_per_logged_hour']:.2f} per logged hour instead of €{fx['talent_eur_per_logged_hour']:.2f}. In total
they earn {eur((ex['talent_eur'] - fx['talent_eur']) * 100)} more because there is more work. The gate holds a floor
of €6 per logged hour so the service level is not bought with the talents' pay.

## Pay

{b['_sessions']:,} sessions, {b['_events']:,} events, {b['_duplicates']:,} of them repeats. Truth: productive seconds
in the world, after-call work capped by the client contract, €0.24 per minute, integer cents.

| ledger | overpaid | underpaid | talents paid wrong | held-out H1 |
|---|---|---|---|---|
{chr(10).join(brows)}

Events are stored once by their id and folded per session by the app's own sequence number, never by arrival order
or device clock. A week's statement is never changed once issued: work that arrives late adds an adjustment row with
the difference, and asking again with nothing new adds nothing.

## Call quality

{q['_calls']:,} calls, {q['_checks']:,} guideline checks, {q['_promise_breaches']} broken promises. The model is a
stand-in in the world: it misses some breaches, flags some clean calls, and its confidence is only partly honest.

| design | broken promises found | all breaches found | clean checks flagged | people's time | held-out H1 |
|---|---|---|---|---|---|
{chr(10).join(qrows)}

Reading every call would take {q['_all_by_people_hours']} hours. Greeting, identity check and summary are fixed
phrases, so rules check them. A promise needs judgement, so the model reads the agent's lines (never the customer's).
Code sends a call to a person when the model is under 0.85 confident, or when it says "fine" but the agent used a
word like promise or guarantee.

## Claims under load

{a['claims']} claims from {a['claims'] - a['claims'] // 5} talents (every fourth taps twice) for one shift with
{a['seats']} seats, 32 at a time: {a['seats_taken']} seats taken by {a['talents_with_a_seat']} talents,
{a['double_bookings']} double bookings, and everyone else told the shift is full. A repeat claim returns the seat the
talent already has. Which talents win changes from run to run; that it is exactly one per seat does not.

## Gate

The gate was written after the first dev results and before the held-out world was run (`config/gate.yaml`). Dev
numbers are after the fixes that came out of the held-out run. H1 numbers are from its one run, before them.

| line | dev | held-out H1 |
|---|---|---|
{chr(10).join(gate)}

Dev passes {passed} of {len(dev['gate'])} lines. H1 passed {hpassed} of {len(held['gate']) if held else 0}:
- the surges were bigger and the pool thinner, and call-outs stopped at the shift change;
- a less honest model sent more calls to people than the gate allows.

[docs/heldout.md](docs/heldout.md) has the detail: what was fixed and measured on dev, and what is open.

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q                                # staffing, ledger, call checks, API race, invariants: seconds
python -m tse.eval.cli evaluate                    # three staffing designs, ledger, call checks and the gate
TSE_SERVE=1 uvicorn tse.product.api:app            # the API, on SQLite in memory unless TSE_DB is set
docker compose up --build                          # API on Postgres, Prometheus :9090, Grafana :3000
pre-commit install                                 # ruff, the fast tests and the README check before each commit
cd web && npm ci && npm run dev                    # the dashboard
```

Where things live:
- `tse/world`: the marketplace and its truth, including the stand-in model;
- `tse/product`: what would ship, which never imports the world;
- `tse/eval`: designs, scoring, gate and this README;
- `web`: the dashboard, which reads the same reports;
- `ops`: Prometheus scrape config and the Grafana dashboard.

[docs/agentic-workflow.md](docs/agentic-workflow.md) describes how this was built with a coding agent: where it
helped, where it went wrong, and the checks that caught it.
"""

# Working in talent-shift-exchange

Fast feedback first: `python -m pytest -q` checks staffing, the allocation rules, the pay ledger, the call checks,
the API with a concurrent claim race, and the invariants, in seconds. `python -m tse.eval.cli evaluate` runs the
three staffing designs for three weeks, the ledger, the call checks and the gate in under ten seconds.
`cd web && npm test && npm run typecheck` checks the dashboard. After a change to the product, the world or the
settings:

```bash
python -m tse.eval.cli evaluate && python -m tse.eval.cli readme && cp reports/dev.json web/public/dev.json
```

and commit `reports/dev.json`, `web/public/dev.json` and `README.md`. CI checks that the README matches the reports,
that a fresh run reproduces `reports/dev.json` exactly, and runs the API tests against Postgres. `pre-commit install`
runs ruff, the fast tests and the README check before each commit.

## Layout

| path | what it is | may import |
|---|---|---|
| `tse/world` | the marketplace: projects, calls, talents and their no-shows, transcripts, app events, the stand-in model, the truth | `tse/keyed.py` |
| `tse/product` | Erlang C, forecast, exchange (plan, allocation, call-outs), pay ledger, call checks, store, API | nothing outside `tse/product` |
| `tse/eval` | the designs, the weekly run, scoring, gate, README, CLI | everything |
| `web` | the dashboard: React, TypeScript, Motion, feature-first, reads `public/dev.json` | the report |
| `config` | world files, the exchange's settings, the gate | |
| `ops` | Prometheus scrape config, Grafana provisioning and dashboard, used by `docker-compose.yml` | |

## Invariants (checked in the tests)

1. **The truth stays in the world.** `tse/product` never imports `tse/world` or `tse/eval`. It gets call counts as
   the phone system reports them, shift requests, logins, app events and transcripts.
2. **The world does not read the exchange's settings.** `tse/world` reads its world file only.
3. **Same luck for every design.** Every draw is keyed by what it is about (`tse/keyed.py`). Every design meets the
   same calls, the same requests, the same no-shows and the same answers to call-out offers.
4. **The model reads and code decides.** The model gives a verdict and a confidence. Code decides whether that is
   enough or a person reads the call. The model only ever sees the agent's lines.
5. **Pay is integer cents, once.** Events are stored once by id and folded by the app's sequence number. An issued
   statement is never changed; late work adds an adjustment row.
6. **A seat is a row.** Claims are correct because of unique constraints in the database, not locks in Python.
7. **Settings in config.** Service target, shrinkage, overbooking, fairness, call-out rules, the review threshold and
   the pay rate live in `config/exchange.yaml`. The dashboard's colours, sizes and durations live in
   `web/src/shared/theme.css` and `tokens.ts`.
8. **Generated reports.** README numbers come from `reports/`.

## The held-out rule

`config/heldout.yaml` (world H1) was written before the first result on it. It was run once
(`python -m tse.eval.cli heldout`), which wrote `config/heldout.lock` and `reports/heldout.json`. The findings are in
`docs/heldout.md`. Fixes are made and measured on dev. The held-out world is not run again, and `config/gate.yaml`
is not moved.

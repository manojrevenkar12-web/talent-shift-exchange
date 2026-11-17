# Building this with a coding agent

This repository was built with Claude Code doing most of the typing, and a person deciding what to build, what counts
as done and which numbers matter. This note records where the agent helped, where it was wrong, and what caught it.
The same setup is what a team would need to use coding agents safely on a product like this.

## The setup that makes agent work checkable

- **The truth is in a separate package.** `tse/world` simulates the marketplace; `tse/product` never imports it, and a
  test fails if it does. An agent cannot make a number look good by reading the answer.
- **Numbers are generated, not written.** The README is rendered from `reports/` and CI fails if it drifts
  (`readme --check`). An agent cannot claim a result the code did not produce.
- **The gate is written before the held-out run, and the run happens once.** `config/heldout.lock` records the
  commit. Fixes are measured on dev. This stops the loop of tuning until a test passes.
- **Settings live in config.** Thresholds and rates are in `config/exchange.yaml`, so a change to policy is a
  reviewable diff and not a constant buried in code.
- **`AGENTS.md` and `CLAUDE.md`** give the agent the invariants and the fast commands, so each session starts from the
  same rules.

## Where the agent helped

- Erlang C staffing, the forecaster and the allocation passes, with tests, in one sitting.
- The SQLAlchemy model. The agent put correctness in unique constraints rather than Python locks, so the claim race
  is safe on SQLite and Postgres alike. CI runs it on both.
- Test scaffolding: the concurrent claim race, the out-of-order event cases, and the invariant tests.
- The README generator, the Prometheus metrics and Grafana dashboard, and the dashboard's loading, error and empty
  states.

## Where it was wrong, and what caught it

1. **Transcripts with the speakers swapped.** The first world labelled every other line "customer" by position. The
   rules would have checked the customers' words for the agent's greeting. Caught by printing one transcript before
   any result existed.
2. **Surges in the training weeks.** Surges were keyed to absolute weeks, which put all of them in the history the
   forecaster learns from, so the "unforecast" surges were forecast. Caught by reading the world file against the
   simulation loop.
3. **Call-outs leaving early.** An off-by-one dropped call-out talents one half hour before their two hours were up.
   Caught on review of the loop.
4. **Paying the same work twice.** The first statement endpoint paid all of a talent's events in every period, so the
   second week's statement would have paid the first week again. Caught while writing the README's sentence about
   late events, because the sentence was not true. Now each week's statement folds only that week's sessions, issued
   rows are never changed, and late work adds an adjustment row. A test covers it.
5. **A wrong test.** The agent wrote a test that expected arrival-order billing to fail on a case it actually handles.
   The code was right and the test was wrong. The fix was a harder case, not a change to the code.

None of these would have shown up as a failing test on their own. Each was caught by a person reading output or
prose against the code. That is the part of the work an agent does not replace.

## What a person decided

- What "good" means: the €6 per logged hour floor for talents, the 80/20 service target, and that people read at most
  a quarter of what reading every call would cost.
- What counts as fair between talents (unmet hours raise priority) and how much overbooking is acceptable (25%).
- What the held-out world should stress, and that its results are reported as they came out.

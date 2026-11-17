# The held-out run

World H1 (`config/heldout.yaml`) was written before the first result on it and run once, at commit 5f0329e, with the
code and settings dev ended on (`config/heldout.lock`). It changed things on purpose:
- 380 talents instead of 420, who no-show more (4–25% each);
- more volume, and handle times on two projects that grew past the client contract the exchange plans with;
- four surges, one of them 2.2× for six hours on the biggest project;
- twice the repeated and late events, and device clocks off by up to five minutes;
- a worse model, whose confidence is honest less often;
- agents who break the no-promise rule in words that are not on the product's hint list.

It passed 11 of 13 gate lines.

## What held

- **Service level:** 81.9% of calls answered in 20 s and 82.5% of half hours on target, against 52.2% for the fixed
  roster. The week was short of talents before any surge: the exchange could book only 91% of what the plan needed.
- **Fairness:** no talent got under half the hours they asked for.
- **Pay:** with 26,877 repeated events and clocks off by minutes, no talent was paid a cent wrong. Reading events in
  arrival order would have got 12.3% of pay wrong, nearly all of it underpaid, for 379 of 380 talents.
- **Claims:** the race gave 40 seats to 40 talents.
- **Call quality:** 99.2% of broken promises found. The model alone found 82.8% and flagged 110 clean checks. The
  product flagged 14.

## What failed

**Surges: 36.6% answered in 20 s, against a line of 50%.**

The 2.2× surge on telco_de needed about 50 people for six hours. Three things kept the exchange short:
- **Call-outs ended at the shift change.** The six-hour surge ran from 9:00 to 15:00, so every call-out was cut at
  noon and the gap had to be filled again from nothing.
- **Offers assumed one taker in three.** The exchange offered three times the gap, but in H1 fewer than one in three
  talents took an offer, so each round came back short.
- **The pool was thin.** Fewer talents, more no-shows and longer calls meant the plan was short before the surge
  began. No call-out policy fixes that; it needs more certified talents on the project.

Fixed on dev, not re-run on H1:
- call-outs now run their two hours across the shift change;
- the exchange learns the acceptance rate from its own offers (a Beta prior of one in three) and sizes each round from
  it, up to 60 offers per half hour.

On dev, surge service went from 58.4% to 60.5%, and abandoned calls from 1,835 to 1,583. Talents earned €6.13 per
logged hour instead of €6.21, still above the €6 floor. Whether this would have reached 50% on H1 is not known.

**People's time: 25.6% of what reading every call costs, against a line of 25%.**

The worse model was unsure more often, so code sent more calls to a person. That is the design working: recall
stayed at 99.2%. But it cost 51 hours of review instead of 36 on dev.

Still open. The next step is to set the confidence threshold per guideline from the calls people have already
reviewed, instead of a fixed 0.85. That gives a cheaper queue when the model is honest and a safe one when it is not.

**Three broken promises missed.** All three used wording that is not on the hint list, from a model that was sure and
wrong. A hint list will always be behind how people talk. The fallback is the review sample: a small random share of
calls the model passed goes to a person, so a new phrasing shows up within days. It is not built yet.

# SKILLS.md

## Add a client project

Add it to `config/exchange.yaml` under `projects` with its contracted handle time (`aht_s`), the after-call work the
client pays for (`acw_cap_s`) and its guidelines. Certify talents for it through `POST /talents`. The plan picks it
up from the forecast once there are three weeks of call counts.

## Change the service target or the overbooking

`service.target_share` and `service.answer_within_s` set the 80/20 target. `allocation.overbook_cap` limits how far
above the need the exchange books when talents' show rates say some will not come. Run `evaluate` and check the talent
€ per logged hour: overstaffing is paid by the talents in idle time.

## Add a guideline to the call checks

A fixed phrase (a greeting, a data-protection notice) is a rule in `tse/product/qa.py`. Something that needs judgement
goes to the model, and code decides with `qa.confident`. Add a few calls that keep and break it to the world's
phrase lists, then run `evaluate` and check recall and people's time.

## Pay a week

`POST /statements/{week}?talent=...` folds that week's sessions and issues a statement. Calling it again adds an
adjustment row only if late events changed the total. Issued rows are never edited.

## Serve it

`TSE_SERVE=1 TSE_DB=postgresql+psycopg://... uvicorn tse.product.api:app`. Tables are created on start.

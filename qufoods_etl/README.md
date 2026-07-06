# database/

Owner: Bukolami — schema design, load logic, Neon setup, analysis.

**Start here:** `../exploration/HANDOFF.md` — the "For Bukolami" section covers the locked region
mapping (`STATE_TO_REGION`), the recommended unique constraints (`transaction_id` /
`record_id`), and two columns worth keeping from the cleaning step for the reporting layer's
"data quality issues by location" feature.

Also worth reading:
- `../exploration/DATA_QUALITY_LOG.md` Finding #7 — `order_channel` vs `order_source`
  inconsistency, an open schema question for you to decide on

This folder is yours to structure as you see fit — not pre-populated.

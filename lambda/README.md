# lambda/

Owner: Emmanuel — Lambda build, EventBridge scheduling, S3 ingestion.

**Start here:** `../exploration/HANDOFF.md` — the "For Emmanuel" section spells out exactly which
functions in the `exploration` package to import directly (`clean_order_items`,
`apply_algebraic_imputation`, `build_regression_fallback`, etc.) instead of re-implementing the
cleaning/imputation logic from scratch.

Also worth reading before starting:
- `../exploration/DATA_QUALITY_LOG.md` Finding #1 — the corrected imputation formula
  (`total = subtotal * (1 - discount)`, not subtraction)
- `../exploration/DATA_QUALITY_LOG.md` Finding #6 — the IAM/public-URL access discrepancy that
  needs a team decision before the EventBridge trigger logic gets built

This folder is yours to structure as you see fit — not pre-populated.

# exploration/

Owner: Siyan — data profiling, quality issue resolution, cleaning/imputation logic
(Implementation Plan tasks #8–22).

## What's in here

```
exploration/
├── pyproject.toml              installable package config
├── DATA_QUALITY_LOG.md         every data quality issue found, with evidence and resolution
├── HANDOFF.md                  contract for Emmanuel/Bukolami/Daniel — what to import and why
├── src/exploration/            the actual package — import this from anywhere
│   ├── ingest.py                S3 pull (live + local-sample fallback)
│   ├── reference.py              branch registry, region mapping, menu list
│   ├── branch_repair.py           recovers null branch_name/branch_manager
│   ├── cleaning.py                typo correction (rapidfuzz, 75% cutoff)
│   ├── imputation.py              algebraic solver + regression fallback for missing totals
│   ├── profiling.py               field-level and branch-level profiling
│   └── pipeline.py                run() — the whole thing end to end
├── notebooks/
│   └── 01_exploration.ipynb     the narrative walkthrough — run this first
├── data/
│   ├── reference/               reference_branches.csv, reference_menu_items.csv (canonical)
│   └── sample_batches/          one real batch (from the brief's example URL) for offline dev
├── tests/                       pytest — proves the formula correction and 75% cutoff are right
└── output/                     generated artifacts land here (git-ignored except .gitkeep)
```

## Quick start

```bash
cd exploration
python -m venv .venv && source .venv/bin/activate    # or your preferred env manager
pip install -e ".[dev]"
pytest                                                 # confirms everything still works
jupyter notebook notebooks/01_exploration.ipynb        # the actual walkthrough
```

Works immediately with **zero AWS credentials** — it runs against the bundled sample batch in
`data/sample_batches/` by default. The moment IAM access to `qufoods-raw` is confirmed, flip
`USE_S3 = True` in the notebook (or pass `use_s3=True` to `exploration.pipeline.run()`) and
everything downstream runs unchanged against the live feed.

## The one thing to know before reading anything else

The brief and architecture diagram describe the missing-total imputation formula as
`order_subtotal - discount_applied = total_amount`. **That's wrong.** `discount_applied` is a
percentage (0–1), not a currency amount — the real relationship is
`total_amount = order_subtotal * (1 - discount_applied)`. Full evidence in
`DATA_QUALITY_LOG.md`, Finding #1. Every imputation function in `imputation.py` already uses the
correct formula — this note exists so nobody "fixes" it back to subtraction without reading why.

## Scaling to real data

Everything here was built and tested against one sample batch (26 records). The code is written
to scale with zero changes once pulling from the live bucket — `pull_batches(use_s3=True)` and
`exploration.pipeline.run(use_s3=True)` handle pagination across as many files as
`list_recent_keys()` finds. What WILL need re-checking at scale (flagged in the data quality log
and the notebook):

- The flagged-vs-other branch quality comparison (one batch isn't enough data to confirm the
  brief's claim about BR-06/07 and BR-15/16/17 statistically)
- The regression fallback model (needs ≥30 training rows; the sample batch doesn't have that many)
- The 75% typo-correction cutoff (validated against the typos that happened to appear in this one
  batch — re-check against a larger, more varied sample)

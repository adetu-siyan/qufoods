# QuFoods Data Pipeline

10-day data engineering lab project at Qucoon — building a real ETL pipeline (S3 → Lambda →
PostgreSQL → Streamlit) for a fictional Nigerian QSR chain, as a 5-person team exercise.

Architecture: `EventBridge (5-min schedule) → Lambda (clean + load) → S3 (processed/audit) +
Neon PostgreSQL (analytics) → Streamlit (reports + PDF, optional Bedrock narrative)`.

## Team / folder ownership

| Folder | Owner | Scope |
|---|---|---|
| `exploration/` | Siyan | Data profiling, quality issue resolution, cleaning/imputation logic |
| `lambda/` | Emmanuel | Lambda build, EventBridge scheduling, S3 ingestion |
| `database/` | Bukolami | Schema design, load logic, Neon setup |
| `streamlit/` | Daniel | Reporting application, visualizations, PDF generation |

Project Manager: Felix Frank-Felix · Head of Operations sponsor: same.

## Status

Exploration phase complete — see `exploration/README.md`, `exploration/DATA_QUALITY_LOG.md`, and
`exploration/HANDOFF.md` for what was found and what every other workstream needs to know before
starting BUILD.

**The one thing every workstream needs to know:** the brief's stated imputation formula
(`order_subtotal - discount_applied = total_amount`) is wrong — `discount_applied` is a percentage,
not a currency amount. The real formula is multiplicative:
`total_amount = order_subtotal * (1 - discount_applied)`. Full evidence in
`exploration/DATA_QUALITY_LOG.md`, Finding #1.

## Setup

Each folder is meant to be largely self-contained with its own dependencies (see each folder's own
README once that workstream has set one up). For exploration specifically:

```bash
cd exploration
pip install -e ".[dev]"
pytest
jupyter notebook notebooks/01_exploration.ipynb
```

Copy `.env.example` to `.env` and fill in real values before running anything that touches AWS or
Neon. **Never commit `.env` — it's already in `.gitignore`.**

## Deliverables (per the SOW)

1. GitHub repository — all pipeline code + README explaining how to run it from scratch
2. Results & Approach deck (PowerPoint) — architecture, data quality findings, ≥3 business
   insights, demo recording, "what we'd do differently"
3. One sample generated PDF report from the live Streamlit app

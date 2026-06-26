# streamlit/

Owner: Daniel — Reporting application, visualizations, PDF generation.

**Start here:** `../exploration/HANDOFF.md` — the "For Daniel" section covers two things that will
break your reports if missed: filtering `transaction_status == 'COMPLETED'` before summing
revenue, and handling the rare negative-dwell-time records.

Also worth reading:
- `../exploration/DATA_QUALITY_LOG.md` Finding #5 — FAILED transactions still carry a populated
  `total_amount`
- `../exploration/DATA_QUALITY_LOG.md` Finding #8 — negative dwell time on at least one record

This folder is yours to structure as you see fit — not pre-populated.

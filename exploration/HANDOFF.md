# Exploration → Team Handoff

**From:** Siyan (Exploration) **To:** Emmanuel (Pipeline/Lambda), Bukolami (Database), Daniel (Reporting)

This is the contract for what exploration produced and exactly how to use it. Read the relevant
section for your workstream — you don't need to read all of it.

The package itself lives at `exploration/src/exploration/` and is pip-installable
(`pip install -e exploration/`), so none of this needs to be copy-pasted — `import exploration.X`
and use it directly.

---

## For Emmanuel (Lambda / Pipeline)

Your Lambda cleaning module should do exactly what `exploration.pipeline.run()` does, in the same
order. The fastest path to a correct Lambda is: import these functions directly rather than
re-implementing them.

```python
from exploration.branch_repair import repair_branch_fields
from exploration.cleaning import clean_order_items, TYPO_MATCH_CUTOFF
from exploration.imputation import (
    apply_algebraic_imputation,
    apply_regression_fallback,
    build_regression_fallback,
    sanity_check_imputed,
)
from exploration.reference import load_menu_items
```

**Pipeline order** (this matters — don't reorder):

1. Split raw records into sales / expense (`exploration.pipeline.split_record_types`)
2. Repair branch fields (`repair_branch_fields`) — before anything else touches branch data
3. Typo-correct `order_items` (`clean_order_items`, cutoff = `TYPO_MATCH_CUTOFF` = **75**, not the
   85 originally suggested — see `DATA_QUALITY_LOG.md` Finding #3 for why)
4. Algebraic imputation first (`apply_algebraic_imputation`) — exact, not an estimate, whenever
   exactly one of `{order_subtotal, discount_applied, total_amount}` is missing
5. Regression fallback only for what's left (`build_regression_fallback` +
   `apply_regression_fallback`) — this is for the rarer case of 2+ missing fields at once
6. Sanity check (`sanity_check_imputed`) — flags (doesn't drop) implausible imputed values

**The one thing you absolutely must not get wrong:** the formula is

```python
total_amount = order_subtotal * (1 - discount_applied)
```

**not** `order_subtotal - discount_applied`, even though that's what the brief and the
architecture diagram say. `discount_applied` is a fraction (0–1), not a currency amount. Full
evidence in `DATA_QUALITY_LOG.md`, Finding #1. `exploration.imputation.formula_total()` already
implements this correctly — just call it, don't re-derive it.

**Open item for you specifically:** Finding #6 in the data quality log — the brief says
public-URL access (no AWS creds), the starter notebook's actual code requires
`s3:ListBucket`/`s3:GetObject` via boto3. `exploration.ingest` defaults to the boto3 path. Confirm
with the team / Felix which one Lambda should actually use before you build the EventBridge
trigger logic around it — it changes what permissions your Lambda's execution role needs.

**Also relevant to your 5-minute dedup logic:** `exploration.ingest.list_recent_keys()` is the
same discovery-by-timestamp approach you'll need, just with a longer lookback window (1440 min for
exploration vs. your production 5 min). Same logic, different window — no need to write this from
scratch.

---

## For Bukolami (Database)

**Schema-relevant facts from exploration:**

- **Region mapping is locked**: `exploration.reference.STATE_TO_REGION` — Lagos state → "Lagos";
  Oyo/Ogun/Ondo/Osun → "West"; everything else (FCT, Rivers, Delta, Edo, Enugu, Anambra, Abia,
  Kaduna, Kano, Plateau) → "Other". If your schema stores region as a column rather than deriving
  it at query time, derive it from this mapping so it matches what the reporting layer expects.
- **`transaction_id` is the natural unique constraint for sales** — confirmed zero duplicates in
  the sample batch, and the SOW explicitly calls for it ("transaction ID enforced as a unique
  constraint so repeated or overlapping pipeline runs upsert cleanly"). Same logic for expense
  records on `record_id`.
- **Two new boolean/categorical columns worth keeping from the cleaning step**, not just the final
  cleaned values — useful for the Regional Manager's "data quality issues by location" report:
  - `order_items_typo_fixed` (bool) — whether any item in that order needed correction
  - `total_amount_imputed` (bool) + `imputation_method` (str: `'algebraic' | 'regression' |
    'branch_median_fallback' | None`) — lets Daniel's reports show "X% of this branch's revenue
    figure was imputed, not directly recorded" as a trust indicator.
- **Open schema question for you**: Finding #7 — `order_channel` and `order_source` sometimes
  disagree on the same record. Decide which one is authoritative for channel-based reporting
  before finalizing the sales table schema.

---

## For Daniel (Reporting / Streamlit)

**Things that will break your reports if not handled:**

- **Filter `transaction_status == 'COMPLETED'` before summing revenue.** Some `FAILED` records
  still have a populated `total_amount` — they look identical in shape to a real sale. The brief's
  Branch Manager spec already asks for "failed and refunded transaction rate" as its own metric,
  so this isn't lost information, it just needs to be reported separately, not folded into revenue.
- **Dwell time can be negative** on a small number of records (departure timestamp before arrival
  — a data entry issue, not a calculation bug). The brief asks for "average dwell time, dwell time
  vs order size" — exclude negative-dwell records from that average, or surface them as a
  data-quality indicator (the Regional Manager report already has a slot for "data quality issues
  by location").
- **`imputation_method` is available per-record** — consider surfacing "X% of revenue this period
  was estimated, not directly recorded" somewhere in the reports. Doesn't need to be prominent, but
  it's the kind of caveat a Head of Operations would want available if they ever ask "how
  confident are we in this number?"

---

## Quick reference — what's importable

```
exploration/
├── ingest.py          pull_batches(), list_recent_keys(), load_batches(), load_batch_from_url()
├── reference.py        load_branches(), load_menu_items(), branch_lookup(), STATE_TO_REGION, FLAGGED_BRANCHES
├── branch_repair.py     repair_branch_fields()
├── cleaning.py          clean_order_items(), correct_item_name(), score_candidates(), TYPO_MATCH_CUTOFF
├── imputation.py        formula_total(), algebraic_solve(), apply_algebraic_imputation(),
│                        build_regression_fallback(), apply_regression_fallback(), sanity_check_imputed()
├── profiling.py         field_profile(), branch_quality_profile(), compare_flagged_vs_other(),
│                        duplicate_summary(), plausibility_checks()
└── pipeline.py          run() -- the whole thing end to end, split_record_types()
```

Full worked example with explanations: `exploration/notebooks/01_exploration.ipynb`.
Full reasoning behind every decision: `exploration/DATA_QUALITY_LOG.md`.
Unit tests proving the above is correct: `exploration/tests/` (run with `pytest` from `exploration/`).

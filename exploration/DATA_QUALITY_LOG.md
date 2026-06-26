# QuFoods — Data Quality Log

**Owner:** Siyan (Adetu Siyanbola), Exploration workstream
**Scope:** Implementation Plan tasks #10, #16, #21 · SOW deliverable "Data quality review document"
**Source:** Profiling run against the sample batch `BATCH-96bd24c2-7124-4fb5-93e8-f016bd600d67`
(pulled from the public URL given in the lab brief) using `exploration/notebooks/01_exploration.ipynb`.

This log will be re-run and updated once a multi-day pull from the live `qufoods-raw` bucket is
available — several findings below are flagged as "needs more data" where the sample batch (26
records, one file) is too small to confirm at scale.

---

## Finding #1 — The imputation formula in the brief/architecture diagram is wrong

**Severity: Critical.** This affects every imputed revenue figure downstream if missed.

The brief and the architecture diagram both describe the relationship between the three money
fields as flat subtraction:

> `order_subtotal - discount_applied = total_amount`

Testing this against real records that have all three fields populated shows it does not hold.
`discount_applied` is a **fraction in [0, 1]** — a discount *rate* (0.12 = 12% off), not a currency
amount. The correct relationship is **multiplicative**:

```
total_amount = order_subtotal * (1 - discount_applied)
```

**Evidence** (real records from the sample batch, discount_applied > 0):

| order_subtotal | discount_applied | total_amount (actual) | subtotal − discount (wrong) | subtotal × (1−discount) (correct) |
|---|---|---|---|---|
| 7366.85 | 0.12 | 6482.83 | 7366.73 | **6482.83** ✓ |
| 3484.39 | 0.18 | 2857.20 | 3484.21 | **2857.20** ✓ |
| 3006.26 | 0.14 | 2585.38 | 3006.12 | **2585.38** ✓ |
| 4059.53 | 0.08 | 3734.77 | 4059.45 | **3734.77** ✓ |
| 6675.00 | 0.20 | 5340.00 | 6674.80 | **5340.00** ✓ |

The multiplicative formula matches to the cent on every record checked; the subtraction formula
is off by thousands of naira on each one.

**Resolution:** `exploration/src/exploration/imputation.py` implements only the multiplicative
form (`formula_total()`). The algebraic solver (`algebraic_solve()`) uses this corrected
relationship for all three directions (solving for total, subtotal, or discount when exactly one
is missing).

**Action for the team:** the architecture diagram and any documentation describing this as
subtraction should be corrected before the BUILD phase, so Emmanuel's Lambda cleaning module
doesn't independently re-derive (or worse, not catch) the same issue.

---

## Finding #2 — Misspelled item names (the brief's named issue)

**Severity: Medium — has a clean, validated fix.**

`order_items` is free text; some entries have a swapped letter pair, e.g. `"ocke"` for `"coke"`,
`"chickne wings"` for `"chicken wings"`. Left uncorrected, item-level reporting would silently
double-count the menu (treating the typo and the real item as two different products).

**Resolution:** `exploration.cleaning.clean_order_items()` (built on the starter notebook's
mechanics, upgraded from `difflib` to `rapidfuzz`) fuzzy-matches every item against the canonical
13-item menu and auto-corrects matches above a confidence cutoff. See Finding #3 for why that
cutoff is 75, not the plan's originally suggested 85.

In the sample batch, 5 of 22 sales records (23%) had at least one typo'd item — a meaningfully
high rate, worth re-checking at scale once pulling more data.

---

## Finding #3 — The implementation plan's suggested 85% confidence threshold is too conservative

**Severity: Medium.** This is a correction to our own plan, not the brief — flagged explicitly
since it changes a number the team already agreed on.

The plan suggested 85% confidence as the auto-correction threshold. Checking it against the real
typos found in the sample batch shows two of them — `"ocke"` and `"ckoe"`, both typos of `"coke"`
— score only **75%** similarity, below the suggested cutoff. At 85%, these would silently fail to
get corrected.

The reason: short item names lose more similarity percentage per swapped letter than long ones. A
4-letter swap on `"coke"` costs far more of the string's total length than a 1-letter swap inside
`"chicken wings"` (13 letters).

| Typo | Closest menu match | Similarity score |
|---|---|---|
| `ocke` | coke | 75.0 |
| `ckoe` | coke | 75.0 |
| `chickne wings` | chicken wings | 92.3 |
| `ofada irce` | ofada rice | 90.0 |
| `chicekn wings` | chicken wings | 92.3 |

Checking the other direction — whether lowering the cutoff risks false-matching something that
isn't actually a QuFoods item — the highest score any genuinely off-menu Nigerian dish gets
against this menu is 50 (`"amala"` vs `"chapman"`):

| Off-menu item | Closest menu match | Similarity score |
|---|---|---|
| spaghetti carbonara | plantain | 37.0 |
| pizza | chapman | 33.3 |
| suya | coleslaw | 33.3 |
| amala | chapman | 50.0 |
| moi moi | zobo | 36.4 |
| akara | ofada rice | 40.0 |
| beans | burger | 36.4 |

This leaves a wide, evidence-backed gap (50–75) with nothing observed in between.

**Resolution:** `TYPO_MATCH_CUTOFF` in `exploration/src/exploration/cleaning.py` is set to **75**,
not 85. Documented here so the change is visible to the team rather than silent.

**Needs more data:** this gap was checked against a 13-item menu and a handful of plausible
off-menu dishes — it's a reasonable cutoff but should be re-validated once a larger sample of real
typos (and real off-menu attempts, if any occur) is available from the live feed.

---

## Finding #4 — `branch_name` / `branch_manager` nulls are a digitisation artifact, not real gaps

**Severity: Low — has a clean, deterministic fix.**

Some sales and expense records arrive with `branch_name` (and occasionally `branch_manager`) set
to `null`, while `branch_id` is always present and the branch registry (`reference_branches.csv`)
is internally consistent and complete (all 20 branches present, one row each).

**Resolution:** `exploration.branch_repair.repair_branch_fields()` recovers these fields via a
deterministic lookup keyed on `branch_id`, rather than dropping the row or leaving it blank. If a
`branch_id` ever fails to resolve against the registry (which would indicate a more serious
problem — a branch that doesn't exist in the reference data at all), the function raises a
warning rather than silently failing.

---

## Finding #5 — `transaction_status: FAILED` records still carry a populated `total_amount`

**Severity: Medium — affects every naive revenue aggregation.**

Some sales records have `transaction_status = "FAILED"` but still have non-null `order_subtotal`
and `total_amount` values populated, identical in shape to a completed sale. A revenue report that
sums `total_amount` without filtering on `transaction_status` would overstate real revenue by
including money that was never actually collected.

**Resolution:** not fixed at the exploration layer (this isn't a data error — failed transactions
legitimately have a subtotal, since the customer did attempt to order something). Instead, flagged
explicitly as a **reporting-layer requirement**: every revenue aggregation in Daniel's Streamlit
reports must filter to `transaction_status == "COMPLETED"` (or report failed/refunded rate as its
own explicit metric, which the brief's "Branch Manager" report spec already asks for — "failed and
refunded transaction rate").

---

## Finding #6 — Discrepancy between the brief's stated access method and the starter notebook's actual code

**Severity: Process — needs a team decision, not a code fix.**

The brief states files in `qufoods-raw` are fetchable via public URL with no AWS credentials
needed. The starter notebook's `list_recent_keys()` / `load_batches()` functions, however, use
`boto3` and explicitly require `s3:ListBucket` + `s3:GetObject` IAM permissions — which only makes
sense if credential-based access is actually required.

**Resolution:** `exploration.ingest` defaults to the boto3 path (matching the starter notebook and
the SOW's stated IAM assumption — see SOW Appendix A, Planning step 1: "secure IAM permissions
(ListBucket, GetObject) on the raw S3 bucket"). A `load_batch_from_url()` fallback exists for the
public-URL path described in the brief, but isn't used by default.

**Action for the team:** raise this with whoever manages the bucket / the project sponsor (Felix,
per the SOW) — confirm which access method is actually intended before BUILD, since Emmanuel's
Lambda needs to know definitively which one to implement (a Lambda with no IAM role can't use
boto3; a Lambda that needs to whitelist a fixed set of public URLs can't discover new files on its
own).

---

## Finding #7 — `order_channel` and `order_source` sometimes disagree

**Severity: Low-medium — a reporting-layer ambiguity, not a hard error.**

Example from the sample batch: a record with `order_channel = "IN_STORE"` but
`order_source = "ONLINE"`. These two fields look like they should be redundant (or at least
consistent) but aren't always.

**Resolution:** not resolved at the exploration layer — flagged as a schema question for Bukolami.
Whichever field becomes authoritative for channel-based reporting (the brief's "channel breakdown"
metric) should be a documented decision, not an assumption baked silently into the database schema.

---

## Finding #8 — At least one record has `customer_departure_time` before `customer_arrival_time`

**Severity: Low — affects dwell-time metrics only.**

The brief's Branch Manager report spec asks for "average dwell time, dwell time vs order size" —
this only works if departure is always after arrival. At least one record in the sample batch
violates this (a timestamp data-entry issue, not a calculation bug).

**Resolution:** flagged at the exploration layer (`Part 11` of the notebook computes this check
directly); not silently corrected, since there's no way to know which of the two timestamps is
actually wrong without more context. Recommend the reporting layer either excludes negative-dwell
records from the dwell-time metric specifically, or surfaces them as their own data-quality
indicator per branch (the Regional Manager report already asks for "data quality issues by
location," so this slots in naturally).

---

## Finding #9 — order_subtotal range sanity and empty order_items on completed sales

**Severity: Low (in this sample) — but the check needed to exist, and didn't.**

Two range/plausibility checks task #10 calls for ("check ranges") but that simple null-rate
profiling doesn't surface on its own:

1. **order_subtotal range sanity.** `order_subtotal` is the one money field the brief describes as
   "always present" and that's never imputed — so a negative, zero, or implausibly large value
   here points to an upstream ingestion problem, not something to silently work around. Checked
   with an IQR-based outlier fence (adapts to real branch spend patterns rather than a hardcoded
   NGN figure) plus a hard non-positive check.
2. **Empty `order_items` on a `COMPLETED` sale.** A completed transaction with a populated
   `total_amount` but no items listed implies money changed hands for nothing — checked separately
   from `FAILED` transactions, where an empty `order_items` is plausible.

**Result on the sample batch:** zero anomalies of either kind — `order_subtotal` ranges from
₦492.38 to ₦12,172.71, all positive, all well inside a reasonable outlier fence (₦24,354.66); every
`COMPLETED` sale has at least one item. Implemented as
`exploration.profiling.plausibility_checks()`, wired into the standard `pipeline.run()` output
(`result.plausibility`) so it runs automatically, not just on demand.

**Needs re-validation at scale:** with only 22 sales records, this is a weak test of whether the
checks would actually catch something on real, larger data. Re-run once pulling from the live
bucket.

---

## Finding #10 — A real bug was found and fixed in this package's own sanity check

**Severity: Was Critical, now Resolved.** Documented here in the interest of transparency, since
finding bugs in your own QA logic and being upfront about it matters more than pretending the
first version was correct.

The original `sanity_check_imputed()` flagged an imputed `total_amount` as implausible if it
exceeded `order_subtotal`. This works fine for algebraically-imputed rows (which always have
`order_subtotal` available, by definition of the algebraic solver). But for rows imputed via the
**regression fallback** — which exists specifically for the case where 2+ of the three money
fields are missing at once — `order_subtotal` is frequently *also* missing on exactly those rows.

`total_amount > order_subtotal` evaluates to `NaN` (not `True` or `False`) when `order_subtotal`
is null, and pandas treats `NaN` as falsy inside a boolean mask. The practical effect: every
regression-fallback row silently skipped the implausibility check entirely, no matter how
nonsensical the predicted value was — the exact rows where a sanity check matters most, since
they're the least-constrained imputation method in the pipeline.

**Resolution:** the check now branches explicitly. Where `order_subtotal` is available, the
original comparison applies. Where it isn't, a heuristic kicks in instead — flag anything more
than 3x or less than 1/3 of that branch's own median `total_amount` (falling back to the
network-wide median if the branch has no other complete data yet). Confirmed with a regression
test (`test_sanity_check_catches_implausible_value_even_without_subtotal` in
`tests/test_imputation.py`) that a deliberately implausible regression-fallback value is now
correctly caught, while a sane one is not false-flagged.

A second test (`test_regression_fallback_actually_fires_on_two_missing_fields`) was also added to
prove the regression-fallback code path actually produces a sane result end-to-end on synthetic
data with 2+ missing fields — this path existed in the code before but had never actually been
exercised by a test, only proven not to crash.

---

## Summary table

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | Imputation formula is multiplicative, not subtractive | Critical | Resolved in code |
| 2 | Misspelled item names | Medium | Resolved in code |
| 3 | 85% threshold too conservative; corrected to 75% | Medium | Resolved in code |
| 4 | branch_name/branch_manager nulls — digitisation artifact | Low | Resolved in code |
| 5 | FAILED transactions still carry total_amount | Medium | Flagged for reporting layer |
| 6 | Brief vs. starter notebook disagree on S3 access method | Process | Needs team decision |
| 7 | order_channel vs order_source inconsistency | Low-medium | Flagged for database schema |
| 8 | Negative dwell time on at least one record | Low | Flagged for reporting layer |
| 9 | order_subtotal range / empty items on completed sales | Low (this sample) | Resolved in code |
| 10 | Sanity check silently skipped regression-fallback rows | Was Critical | Fixed + regression-tested |

**Needs re-validation at scale:** Findings #2, #3, #9, and the branch-level quality comparison
(brief's claim about BR-06/07 and BR-15/16/17) are all based on a single 26-record sample batch.
Re-run `exploration/notebooks/01_exploration.ipynb` with `USE_S3 = True` against several days of
real data and update this log once that's done.

"""
exploration.imputation
========================

Implements Implementation Plan tasks #16-20:
  16. Test formula: order_subtotal, discount_applied, total_amount relationship
  17. Decide imputation method based on formula match rate
  18. Build algebraic solve for any single missing field
  19. Build regression fallback (scikit-learn) only if formula check fails
  20. Sanity check all imputed values — reject negatives or implausible results

THE FORMULA — CORRECTED FROM THE BRIEF/ARCHITECTURE DIAGRAM
-------------------------------------------------------------
The brief and the architecture diagram describe the relationship as
`order_subtotal - discount_applied = total_amount` (a flat subtraction).
Checking that against real records with all three fields present shows
this is wrong: `discount_applied` is a **fraction in [0, 1]** (a discount
*rate*, e.g. 0.12 = 12% off), not a currency amount. The correct relationship
is multiplicative:

    total_amount = order_subtotal * (1 - discount_applied)

Verified against five real records with discount_applied > 0 in the sample
batch — exact match (to the cent) on every one; the subtraction formula is
off by thousands of naira on each. This is documented as Data Quality Log
Finding #1 — it's the single most important finding in this section, since
every algebraic imputation downstream is wrong if this gets missed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Tolerance for floating point comparison when checking the formula against
# rows that already have all three fields. 1 kobo (NGN 0.01) is generous
# enough to absorb rounding, tight enough to catch a real mismatch.
FORMULA_TOLERANCE = 0.01


def formula_total(subtotal: float, discount: float) -> float:
    """The corrected formula: total = subtotal * (1 - discount_rate)."""
    return subtotal * (1 - discount)


@dataclass
class FormulaValidationResult:
    n_checked: int
    n_match: int
    match_rate: float
    example_mismatches: pd.DataFrame

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"FormulaValidationResult(n_checked={self.n_checked}, "
            f"n_match={self.n_match}, match_rate={self.match_rate:.2%})"
        )


def validate_formula(sales_df: pd.DataFrame, tolerance: float = FORMULA_TOLERANCE) -> FormulaValidationResult:
    """Task #16 — test the formula against every row where all three fields
    are present, and report the match rate.

    A high match rate (expect ~100% once you're using the multiplicative
    form) is what justifies the algebraic-solve-first strategy in task #17:
    if the formula reliably holds, there's no need to reach for a trained
    model on the common case of exactly one missing field — only the rarer
    two-or-more-missing case needs the regression fallback.
    """
    complete = sales_df.dropna(subset=["order_subtotal", "discount_applied", "total_amount"]).copy()
    if complete.empty:
        return FormulaValidationResult(0, 0, 0.0, complete)

    complete["predicted_total"] = formula_total(complete["order_subtotal"], complete["discount_applied"])
    complete["matches"] = (complete["predicted_total"] - complete["total_amount"]).abs() <= tolerance

    n_checked = len(complete)
    n_match = int(complete["matches"].sum())
    detail_cols = [c for c in ["transaction_id", "order_subtotal", "discount_applied", "total_amount", "predicted_total"] if c in complete.columns]
    mismatches = complete.loc[~complete["matches"], detail_cols]

    return FormulaValidationResult(
        n_checked=n_checked,
        n_match=n_match,
        match_rate=n_match / n_checked,
        example_mismatches=mismatches.head(10),
    )


def algebraic_solve(row: pd.Series) -> tuple[float | None, str | None]:
    """Task #18 — solve for whichever single one of {subtotal, discount,
    total} is missing, given the other two. Returns (value, which_field) or
    (None, None) if zero or 2+ fields are missing (caller should route to
    the regression fallback in that case).

    discount_applied = 0 is a valid value (no discount given) and must not
    be confused with missing — `pd.isna` is used throughout, never falsy
    checks, specifically to avoid that bug.
    """
    subtotal, discount, total = row["order_subtotal"], row["discount_applied"], row["total_amount"]
    missing = [name for name, val in [("order_subtotal", subtotal), ("discount_applied", discount), ("total_amount", total)] if pd.isna(val)]

    if len(missing) != 1:
        return None, None

    field = missing[0]
    if field == "total_amount":
        return formula_total(subtotal, discount), field
    if field == "order_subtotal":
        if discount == 1:
            return None, field  # 100% discount makes subtotal unrecoverable from total alone
        return total / (1 - discount), field
    if field == "discount_applied":
        if subtotal == 0:
            return None, field
        return 1 - (total / subtotal), field

    return None, None  # pragma: no cover - unreachable, kept for exhaustiveness


def apply_algebraic_imputation(sales_df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized application of `algebraic_solve` across the sales DataFrame.

    Adds:
      - total_amount_imputed: bool, True where this function filled a value
      - imputation_method: 'algebraic' | 'regression' | None (None = not needed)
    Only fills `total_amount` here (the common missing-data case, per the
    brief). `order_subtotal`/`discount_applied` recovery via the same solver
    is available but not auto-applied, since the brief only ever describes
    `total_amount` as the field that goes missing in practice.
    """
    df = sales_df.copy()
    df["total_amount_imputed"] = False
    df["imputation_method"] = None

    needs_total = df["total_amount"].isna()
    has_both_inputs = df["order_subtotal"].notna() & df["discount_applied"].notna()
    solvable_mask = needs_total & has_both_inputs

    df.loc[solvable_mask, "total_amount"] = formula_total(
        df.loc[solvable_mask, "order_subtotal"], df.loc[solvable_mask, "discount_applied"]
    )
    df.loc[solvable_mask, "total_amount_imputed"] = True
    df.loc[solvable_mask, "imputation_method"] = "algebraic"

    return df


def build_regression_fallback(sales_df: pd.DataFrame):
    """Task #19 — regression fallback, used ONLY for rows where 2+ of
    {subtotal, discount, total} are missing at once (so the algebraic
    solver in task #18 can't be applied).

    Trained on rows that DO have a complete total_amount, using features
    that are essentially always present regardless of which other fields
    are missing: branch_id (one-hot), order_channel, payment_method, and
    item count. This deliberately excludes order_subtotal/discount_applied
    as features, since by definition the rows that need this fallback are
    missing one or both of those — a model trained to depend on them would
    be unusable on exactly the rows it exists to serve.

    Returns the fitted pipeline, or None if there isn't enough complete
    data to train responsibly (caller should fall back to a branch-level
    median in that case — see `apply_regression_fallback`).
    """
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    MIN_TRAINING_ROWS = 30  # below this, a trained model is more confident than the data warrants

    train_df = sales_df.dropna(subset=["total_amount", "branch_id", "order_channel", "payment_method"]).copy()
    train_df["n_items"] = train_df["order_items"].fillna("").apply(
        lambda s: len([p for p in str(s).split(",") if p.strip()])
    )

    if len(train_df) < MIN_TRAINING_ROWS:
        return None

    features = ["branch_id", "order_channel", "payment_method", "n_items"]
    categorical = ["branch_id", "order_channel", "payment_method"]

    preprocessor = ColumnTransformer(
        transformers=[("onehot", OneHotEncoder(handle_unknown="ignore"), categorical)],
        remainder="passthrough",
    )
    model = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            ("regressor", RandomForestRegressor(n_estimators=200, random_state=42, max_depth=8, n_jobs=1)),
        ]
    )
    model.fit(train_df[features], train_df["total_amount"])
    return model


def apply_regression_fallback(df: pd.DataFrame, model) -> pd.DataFrame:
    """Apply the trained regression model to rows still missing total_amount
    after the algebraic pass (i.e. rows where 2+ fields were missing).
    """
    df = df.copy()
    still_missing = df["total_amount"].isna()
    if not still_missing.any():
        return df

    if model is None:
        # Not enough training data — fall back to branch-level median rather
        # than a single global number, since branch-level spend patterns
        # vary a lot (Lagos flagship branches vs. smaller regional outlets).
        branch_median = df.groupby("branch_id")["total_amount"].median()
        global_median = df["total_amount"].median()
        df.loc[still_missing, "total_amount"] = df.loc[still_missing, "branch_id"].map(branch_median).fillna(global_median)
        df.loc[still_missing, "imputation_method"] = "branch_median_fallback"
        df.loc[still_missing, "total_amount_imputed"] = True
        return df

    subset = df.loc[still_missing].copy()
    subset["n_items"] = subset["order_items"].fillna("").apply(
        lambda s: len([p for p in str(s).split(",") if p.strip()])
    )
    features = ["branch_id", "order_channel", "payment_method", "n_items"]
    predictions = model.predict(subset[features])

    df.loc[still_missing, "total_amount"] = predictions
    df.loc[still_missing, "imputation_method"] = "regression"
    df.loc[still_missing, "total_amount_imputed"] = True
    return df


def sanity_check_imputed(df: pd.DataFrame) -> pd.DataFrame:
    """Task #20 — reject implausible imputed values.

    Rules:
      - imputed total_amount must be >= 0 (never a negative bill)
      - if order_subtotal IS available, imputed total_amount must not exceed
        it (a "total" bigger than the pre-discount subtotal is never
        correct, since discount_applied can't be negative in this dataset)
      - if order_subtotal is NOT available (the regression-fallback case,
        where 2+ fields were missing at once), there's nothing to bound the
        upper end algebraically — instead, flag anything more than 3x the
        branch's own median total_amount as worth a second look. This is a
        heuristic, not a hard rule, since "implausible" without a subtotal
        to check against can only ever be a judgment call.

    BUG FIX (found during review): `df["total_amount"] > df["order_subtotal"]`
    silently evaluates to NaN -- not True -- when order_subtotal is also
    null, and pandas treats NaN as falsy in a boolean mask. That meant rows
    imputed via the regression fallback (which by definition often lack
    order_subtotal too) were NEVER actually checked, regardless of how
    implausible the predicted value was. Fixed by branching explicitly on
    whether order_subtotal is present before deciding which check applies.

    Rows that fail are flagged, not silently dropped — a human should look
    at WHY the imputation produced a nonsense value (likely a deeper data
    issue on that record) rather than have it disappear quietly.
    """
    df = df.copy()
    df["imputation_flagged_implausible"] = False

    imputed_mask = df.get("total_amount_imputed", pd.Series(False, index=df.index)) == True  # noqa: E712
    if not imputed_mask.any():
        return df

    negative = imputed_mask & (df["total_amount"] < 0)

    has_subtotal = df["order_subtotal"].notna()
    exceeds_subtotal = imputed_mask & has_subtotal & (df["total_amount"] > df["order_subtotal"] + FORMULA_TOLERANCE)

    # Heuristic check for rows with NO subtotal to bound against (regression
    # fallback case) -- flag anything wildly outside that branch's normal
    # range. Falls back to the global median if a branch has no other data.
    no_subtotal = imputed_mask & ~has_subtotal
    if no_subtotal.any():
        branch_median = df.loc[df["total_amount_imputed"] != True, :].groupby("branch_id")["total_amount"].median()  # noqa: E712
        global_median = df.loc[df["total_amount_imputed"] != True, "total_amount"].median()  # noqa: E712
        # Build the reference series over the FULL index (not just the
        # no_subtotal subset) so it aligns with df["total_amount"] below --
        # comparing two differently-indexed Series raises in modern pandas.
        reference = df["branch_id"].map(branch_median).fillna(global_median)
        outside_heuristic_range = no_subtotal & (
            (df["total_amount"] > reference * 3) | (df["total_amount"] < reference / 3)
        )
    else:
        outside_heuristic_range = pd.Series(False, index=df.index)

    df.loc[negative | exceeds_subtotal | outside_heuristic_range, "imputation_flagged_implausible"] = True
    return df

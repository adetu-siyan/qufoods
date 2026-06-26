"""
exploration.profiling
======================

Implements Implementation Plan tasks #10 and #11:
  10. Profile every field — null rates, types, ranges, duplicates
  11. Profile branch-level quality — specifically BR-06/07 and BR-15/16/17

All functions take a DataFrame and return a DataFrame/dict summary — no
plotting, no side effects, so they're equally usable from a notebook, a
script, or a future unit test / CI check.
"""

from __future__ import annotations

import pandas as pd


def field_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column profile: dtype, null rate, distinct count, min/max for numerics.

    This is the field-level half of task #10. Run separately on sales_df and
    expense_df — they're different schemas after the record-type split.
    """
    rows = []
    for col in df.columns:
        series = df[col]
        row = {
            "column": col,
            "dtype": str(series.dtype),
            "null_count": int(series.isna().sum()),
            "null_rate": round(float(series.isna().mean()), 4),
            "n_distinct": int(series.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(series):
            non_null = series.dropna()
            row["min"] = float(non_null.min()) if len(non_null) else None
            row["max"] = float(non_null.max()) if len(non_null) else None
        else:
            row["min"] = None
            row["max"] = None
        rows.append(row)

    return (
        pd.DataFrame(rows)
        .sort_values("null_rate", ascending=False)
        .reset_index(drop=True)
    )


def duplicate_summary(df: pd.DataFrame, id_column: str) -> dict:
    """Check for duplicate IDs — matters once the pipeline runs on overlapping
    5-minute windows in production (BUILD/TESTING phases rely on this being
    caught early, in exploration, rather than discovered live).
    """
    if id_column not in df.columns:
        return {"id_column": id_column, "present": False}

    counts = df[id_column].value_counts()
    dupes = counts[counts > 1]
    return {
        "id_column": id_column,
        "present": True,
        "total_rows": len(df),
        "distinct_ids": int(df[id_column].nunique()),
        "duplicate_id_count": int(len(dupes)),
        "duplicate_row_count": int(dupes.sum() - len(dupes)) if len(dupes) else 0,
        "example_duplicate_ids": dupes.index[:5].tolist(),
    }


def plausibility_checks(sales_df: pd.DataFrame) -> dict:
    """Range/plausibility checks that task #10 calls for ("check ranges") but
    that `field_profile` alone doesn't surface — it reports min/max, not
    whether those values make business sense.

    Two checks, found missing during review and added here:

    1. order_subtotal range sanity — order_subtotal is described in the
       brief as "always present" and is the one money field that's never
       imputed, so if IT is ever negative, zero, or implausibly large, that
       points to a problem upstream of anything this package can fix (a
       POS/ingestion bug), not something to silently impute around.

    2. Empty order_items on a COMPLETED sale — a completed transaction with
       a populated total_amount but no items listed is a real anomaly: it
       implies money changed hands for nothing. Worth surfacing explicitly
       rather than letting it pass silently through item-level reporting
       (where it would just look like a transaction with zero items sold,
       no flag raised).

    Returns a dict with two DataFrames (`subtotal_anomalies`,
    `empty_items_on_completed_sales`) plus summary counts — both intended to
    go directly into DATA_QUALITY_LOG.md once run on real, larger data.
    """
    results: dict = {}

    # --- Check 1: order_subtotal range sanity ---
    subtotal = sales_df["order_subtotal"]
    negative_or_zero = subtotal <= 0
    # "Implausibly large" is a judgment call with no ground truth to check
    # against -- using 3x the IQR-based upper fence (a standard outlier rule)
    # rather than a hardcoded NGN figure, so this adapts as real branch-level
    # spend patterns come in instead of being tuned to this one sample batch.
    q1, q3 = subtotal.quantile(0.25), subtotal.quantile(0.75)
    iqr = q3 - q1
    upper_fence = q3 + 3 * iqr if iqr > 0 else subtotal.max()
    implausibly_large = subtotal > upper_fence

    subtotal_anomaly_mask = negative_or_zero | implausibly_large
    results["subtotal_anomalies"] = sales_df.loc[
        subtotal_anomaly_mask,
        [c for c in ["transaction_id", "branch_id", "order_subtotal"] if c in sales_df.columns],
    ].assign(
        reason=lambda d: d["order_subtotal"].apply(
            lambda v: "non_positive" if v <= 0 else "implausibly_large"
        )
    )
    results["n_subtotal_anomalies"] = int(subtotal_anomaly_mask.sum())
    results["subtotal_upper_fence_used"] = round(float(upper_fence), 2)

    # --- Check 2: empty order_items on a COMPLETED sale ---
    if "order_items" in sales_df.columns and "transaction_status" in sales_df.columns:
        items_empty = sales_df["order_items"].isna() | (sales_df["order_items"].astype(str).str.strip() == "")
        is_completed = sales_df["transaction_status"] == "COMPLETED"
        empty_completed_mask = items_empty & is_completed

        results["empty_items_on_completed_sales"] = sales_df.loc[
            empty_completed_mask,
            [c for c in ["transaction_id", "branch_id", "total_amount", "transaction_status"] if c in sales_df.columns],
        ]
        results["n_empty_items_on_completed_sales"] = int(empty_completed_mask.sum())
    else:
        results["empty_items_on_completed_sales"] = pd.DataFrame()
        results["n_empty_items_on_completed_sales"] = 0

    return results


def branch_quality_profile(
    sales_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    flagged_branches: list[str] | None = None,
) -> pd.DataFrame:
    """Per-branch quality scorecard — task #11's deliverable.

    Computes, for every branch, the null rate on the fields that matter most
    for downstream reporting (total_amount, branch_name) and a simple typo
    rate proxy, then flags whether each branch is one of the ones the brief
    specifically called out (BR-06/07 in Ogun, BR-15/16/17 in the south-east).

    The point of comparing flagged vs. non-flagged branches side by side is
    to confirm the brief's claim with evidence rather than taking it on
    faith — and to surface whether any *non-flagged* branch is secretly just
    as bad, which the brief explicitly says is possible ("not the only ones
    you will find").
    """
    if flagged_branches is None:
        from exploration.reference import FLAGGED_BRANCHES as flagged_branches  # noqa: N813

    rows = []
    for branch_id, group in sales_df.groupby("branch_id"):
        rows.append(
            {
                "branch_id": branch_id,
                "n_sales_records": len(group),
                "total_amount_null_rate": round(float(group["total_amount"].isna().mean()), 4),
                "branch_name_null_rate": round(float(group["branch_name"].isna().mean()), 4)
                if "branch_name" in group
                else None,
                "membership_null_rate": round(float(group["membership_id"].isna().mean()), 4)
                if "membership_id" in group
                else None,
                "is_flagged_branch": branch_id in flagged_branches,
            }
        )

    expense_counts = expense_df.groupby("branch_id").size().rename("n_expense_records")

    profile = pd.DataFrame(rows).set_index("branch_id").join(expense_counts, how="left")
    profile["n_expense_records"] = profile["n_expense_records"].fillna(0).astype(int)
    profile = profile.reset_index().sort_values("total_amount_null_rate", ascending=False)
    return profile


def compare_flagged_vs_other(branch_profile: pd.DataFrame) -> pd.DataFrame:
    """Aggregate flagged vs. non-flagged branches into two rows for a quick
    sanity check on whether the brief's claim actually holds in the data.
    """
    summary = (
        branch_profile.groupby("is_flagged_branch")[
            ["total_amount_null_rate", "branch_name_null_rate", "membership_null_rate"]
        ]
        .mean()
        .round(4)
    )
    summary.index = summary.index.map({True: "flagged_branches", False: "other_branches"})
    return summary

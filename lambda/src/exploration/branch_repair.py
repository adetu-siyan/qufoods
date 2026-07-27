"""
exploration.branch_repair
===========================

`branch_name` and `branch_manager` nulls are a digitisation artifact, not a
real data gap — `branch_id` is never null, and the branch registry is always
internally consistent. So we recover these fields with a deterministic
lookup against the reference registry instead of dropping the row or
leaving it blank.

Mirrors the starter notebook's Part 5 exactly, factored into a function so
it can run as part of the unified `pipeline.run()` and be unit tested.
"""

from __future__ import annotations

import pandas as pd

from exploration.reference import branch_lookup


def repair_branch_fields(df: pd.DataFrame, reference_dir=None) -> pd.DataFrame:
    """Fill null `branch_name` (and `branch_manager`, for sales records) by
    mapping `branch_id` against the canonical registry.

    Works for both sales_df (has branch_manager) and expense_df (does not)
    — checks which columns are actually present before touching them.
    """
    df = df.copy()
    lookup = branch_lookup(reference_dir) if reference_dir else branch_lookup()

    if "branch_name" in df.columns:
        df["branch_name"] = df["branch_id"].map(lookup["branch_name"])
    if "branch_manager" in df.columns:
        df["branch_manager"] = df["branch_id"].map(lookup["branch_manager"])

    # Surface anything that STILL doesn't resolve — that's no longer a
    # digitisation artifact, that's a branch_id that doesn't exist in the
    # registry at all, which is a different and more serious problem.
    if "branch_name" in df.columns:
        unresolved = df[df["branch_name"].isna()]["branch_id"].unique().tolist()
        if unresolved:
            import warnings

            warnings.warn(
                f"branch_id values with no match in reference_branches.csv: {unresolved}. "
                "These did not resolve via lookup and need investigation, not silent repair."
            )

    return df

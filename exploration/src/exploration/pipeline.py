"""
exploration.pipeline
======================

Orchestrates the full exploration flow end to end:

    pull -> split sales/expense -> repair branch fields -> fix typos
    -> validate formula -> impute missing totals -> sanity check
    -> profile -> return everything needed for the data quality log

This is the one function other team members (and your own notebooks/CI)
should call to get a fully-cleaned DataFrame without needing to know the
internals of each step. It is deliberately the same shape Emmanuel's Lambda
cleaning module should end up taking — same steps, same order, same
contracts — so that promoting this from "exploration logic" to "production
Lambda logic" is a port, not a redesign.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from exploration.branch_repair import repair_branch_fields
from exploration.cleaning import TYPO_MATCH_CUTOFF, clean_order_items
from exploration.imputation import (
    apply_algebraic_imputation,
    apply_regression_fallback,
    build_regression_fallback,
    sanity_check_imputed,
    validate_formula,
)
from exploration.ingest import IngestResult, pull_batches
from exploration.profiling import (
    branch_quality_profile,
    compare_flagged_vs_other,
    duplicate_summary,
    field_profile,
    plausibility_checks,
)
from exploration.reference import load_menu_items


@dataclass
class PipelineResult:
    """Everything downstream consumers (the data quality log, handoff doc,
    or your own analysis) need, gathered in one place.
    """

    raw_record_count: int
    sales_df: pd.DataFrame
    expense_df: pd.DataFrame
    formula_validation: object
    sales_field_profile: pd.DataFrame
    expense_field_profile: pd.DataFrame
    branch_quality: pd.DataFrame
    flagged_comparison: pd.DataFrame
    duplicate_checks: dict = field(default_factory=dict)
    plausibility: dict = field(default_factory=dict)
    n_typo_corrections: int = 0
    n_algebraic_imputations: int = 0
    n_regression_imputations: int = 0
    n_implausible_imputations: int = 0


def split_record_types(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate the mixed batch into sales and expense frames.

    Mirrors the starter notebook's Part 3 — `dropna(axis=1, how='all')` drops
    columns that are 100% null for that record type (e.g. expense-only
    columns on the sales frame), so each frame only carries its own schema.
    """
    sales_df = raw_df[raw_df["record_type"] == "SALE"].dropna(axis=1, how="all").reset_index(drop=True)
    expense_df = raw_df[raw_df["record_type"] == "EXPENSE"].dropna(axis=1, how="all").reset_index(drop=True)
    return sales_df, expense_df


def run(
    use_s3: bool = False,
    bucket: str = "qufoods-raw",
    minutes: int = 1440,
    profile: str | None = None,
    sample_dir: str = "data/sample_batches",
    typo_cutoff: float = TYPO_MATCH_CUTOFF,
) -> PipelineResult:
    """Run the full exploration pipeline once and return a `PipelineResult`.

    Set `use_s3=True` once AWS credentials are confirmed — every other
    argument and every downstream step is unchanged. This is the single
    switch that takes this from "works on the sample batch" to "works on
    the live feed."
    """
    ingest_result: IngestResult = pull_batches(
        use_s3=use_s3, bucket=bucket, minutes=minutes, profile=profile, sample_dir=sample_dir
    )
    raw_df = ingest_result.raw_df

    sales_df, expense_df = split_record_types(raw_df)

    # Branch field repair (digitisation artifact, not a real gap)
    sales_df = repair_branch_fields(sales_df)
    if "branch_name" in expense_df.columns:
        expense_df = repair_branch_fields(expense_df)

    # Typo correction
    menu_ref = load_menu_items()
    cleaned = sales_df["order_items"].apply(lambda v: clean_order_items(v, menu_ref, typo_cutoff))
    sales_df["order_items_clean"] = cleaned.apply(lambda t: t[0])
    sales_df["order_items_typo_fixed"] = cleaned.apply(lambda t: t[1])
    n_typo_corrections = int(sales_df["order_items_typo_fixed"].sum())

    # Formula validation, BEFORE imputation overwrites any nulls — this has
    # to run on the as-received data so the match rate reflects reality.
    formula_validation = validate_formula(sales_df)

    # Imputation: algebraic first, regression fallback only for what's left
    sales_df = apply_algebraic_imputation(sales_df)
    n_algebraic = int((sales_df["imputation_method"] == "algebraic").sum())

    model = build_regression_fallback(sales_df)
    sales_df = apply_regression_fallback(sales_df, model)
    n_regression = int(sales_df["imputation_method"].isin(["regression", "branch_median_fallback"]).sum())

    sales_df = sanity_check_imputed(sales_df)
    n_implausible = int(sales_df["imputation_flagged_implausible"].sum())

    # Profiling — runs AFTER cleaning so the profile reflects what actually
    # ships downstream, but duplicate checks run on transaction_id /
    # record_id regardless of cleaning state since IDs aren't touched by it.
    sales_profile = field_profile(sales_df)
    expense_profile = field_profile(expense_df)
    branch_quality = branch_quality_profile(sales_df, expense_df)
    flagged_comparison = compare_flagged_vs_other(branch_quality)

    duplicate_checks = {
        "sales": duplicate_summary(sales_df, "transaction_id"),
        "expense": duplicate_summary(expense_df, "record_id"),
    }
    plausibility = plausibility_checks(sales_df)

    return PipelineResult(
        raw_record_count=len(raw_df),
        sales_df=sales_df,
        expense_df=expense_df,
        formula_validation=formula_validation,
        sales_field_profile=sales_profile,
        expense_field_profile=expense_profile,
        branch_quality=branch_quality,
        flagged_comparison=flagged_comparison,
        duplicate_checks=duplicate_checks,
        plausibility=plausibility,
        n_typo_corrections=n_typo_corrections,
        n_algebraic_imputations=n_algebraic,
        n_regression_imputations=n_regression,
        n_implausible_imputations=n_implausible,
    )

"""
exploration.pipeline
======================

Orchestrates the full exploration flow end to end:

    pull -> split sales/expense -> repair branch fields -> fix typos
    -> validate formula -> impute missing totals -> sanity check
    -> profile -> save cleaned CSVs -> return everything needed for the data quality log

This is the one function other team members (and your own notebooks/CI)
should call to get a fully-cleaned DataFrame without needing to know the
internals of each step. It is deliberately the same shape Emmanuel's Lambda
cleaning module should end up taking — same steps, same order, same
contracts — so that promoting this from "exploration logic" to "production
Lambda logic" is a port, not a redesign.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

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


OUTPUT_DIR = Path(__file__).resolve().parents[3] / "output"


@dataclass
class PipelineResult:
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
    sales_df = raw_df[raw_df["record_type"] == "SALE"].dropna(axis=1, how="all").reset_index(drop=True)
    expense_df = raw_df[raw_df["record_type"] == "EXPENSE"].dropna(axis=1, how="all").reset_index(drop=True)
    return sales_df, expense_df


def save_outputs(sales_df: pd.DataFrame, expense_df: pd.DataFrame, output_dir: Path = OUTPUT_DIR) -> None:
    """Append cleaned sales and expense records to the output CSVs.

    Files are always named:
        output/sales.csv
        output/expenses.csv

    First run creates the files. Every subsequent run appends new rows
    to the bottom — so one growing file accumulates all cleaned batches
    over time, rather than creating a new file per batch or overwriting
    previous data.

    Bukolami reads directly from these two files. Once Emmanuel's Lambda
    is live, it writes directly to Neon Postgres instead and these CSVs
    become redundant.
    """
    os.makedirs(output_dir, exist_ok=True)
    sales_path = output_dir / "sales.csv"
    expense_path = output_dir / "expenses.csv"

    sales_file_exists = sales_path.exists()
    expense_file_exists = expense_path.exists()

    sales_df.to_csv(sales_path, mode='a', header=not sales_file_exists, index=False)
    expense_df.to_csv(expense_path, mode='a', header=not expense_file_exists, index=False)

    print(f"Cleaned data appended to {output_dir}/")
    print(f"  - sales.csv     (+{len(sales_df)} new records)")
    print(f"  - expenses.csv  (+{len(expense_df)} new records)")


def run(
    use_s3: bool = False,
    bucket: str = "qufoods-raw",
    minutes: int = 1440,
    profile: str | None = None,
    sample_dir: str = "data/sample_batches",
    typo_cutoff: float = TYPO_MATCH_CUTOFF,
    save: bool = True,
) -> PipelineResult:
    """Run the full exploration pipeline once and return a PipelineResult.

    Set use_s3=True once AWS credentials are confirmed.
    Set save=False to run without writing CSVs to disk.
    """
    ingest_result: IngestResult = pull_batches(
        use_s3=use_s3, bucket=bucket, minutes=minutes, profile=profile, sample_dir=sample_dir
    )
    raw_df = ingest_result.raw_df

    sales_df, expense_df = split_record_types(raw_df)

    # Branch field repair
    sales_df = repair_branch_fields(sales_df)
    if "branch_name" in expense_df.columns:
        expense_df = repair_branch_fields(expense_df)

    # Typo correction
    menu_ref = load_menu_items()
    cleaned = sales_df["order_items"].apply(lambda v: clean_order_items(v, menu_ref, typo_cutoff))
    sales_df["order_items_clean"] = cleaned.apply(lambda t: t[0])
    sales_df["order_items_typo_fixed"] = cleaned.apply(lambda t: t[1])
    n_typo_corrections = int(sales_df["order_items_typo_fixed"].sum())

    # Formula validation BEFORE imputation overwrites any nulls
    formula_validation = validate_formula(sales_df)

    # Imputation: algebraic first, regression fallback only for what's left
    sales_df = apply_algebraic_imputation(sales_df)
    n_algebraic = int((sales_df["imputation_method"] == "algebraic").sum())

    model = build_regression_fallback(sales_df)
    sales_df = apply_regression_fallback(sales_df, model)
    n_regression = int(sales_df["imputation_method"].isin(["regression", "branch_median_fallback"]).sum())

    sales_df = sanity_check_imputed(sales_df)
    n_implausible = int(sales_df["imputation_flagged_implausible"].sum())

    # Profiling
    sales_profile = field_profile(sales_df)
    expense_profile = field_profile(expense_df)
    branch_quality = branch_quality_profile(sales_df, expense_df)
    flagged_comparison = compare_flagged_vs_other(branch_quality)
    plausibility = plausibility_checks(sales_df)

    duplicate_checks = {
        "sales": duplicate_summary(sales_df, "transaction_id"),
        "expense": duplicate_summary(expense_df, "record_id"),
    }

    # Save cleaned CSVs automatically
    if save:
        save_outputs(sales_df, expense_df)

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
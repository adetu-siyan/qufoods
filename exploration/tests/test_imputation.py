"""
Tests for exploration.imputation — most importantly, proves the corrected
multiplicative formula (total = subtotal * (1 - discount)) against real
records pulled from the sample batch, since getting this wrong silently
corrupts every revenue figure downstream.
"""

import pandas as pd
import pytest

from exploration.imputation import (
    algebraic_solve,
    apply_algebraic_imputation,
    apply_regression_fallback,
    build_regression_fallback,
    formula_total,
    sanity_check_imputed,
    validate_formula,
)

# Five real records from the sample batch with discount_applied > 0,
# transcribed exactly. total_amount here is what S3 actually returned.
REAL_DISCOUNTED_RECORDS = [
    {"order_subtotal": 7366.85, "discount_applied": 0.12, "total_amount": 6482.83},
    {"order_subtotal": 3484.39, "discount_applied": 0.18, "total_amount": 2857.20},
    {"order_subtotal": 3006.26, "discount_applied": 0.14, "total_amount": 2585.38},
    {"order_subtotal": 4059.53, "discount_applied": 0.08, "total_amount": 3734.77},
    {"order_subtotal": 6675.00, "discount_applied": 0.20, "total_amount": 5340.00},
]


@pytest.mark.parametrize("record", REAL_DISCOUNTED_RECORDS)
def test_multiplicative_formula_matches_real_data(record):
    """The brief/architecture diagram describe subtraction; real data proves
    it's multiplicative. This is THE key finding of the exploration phase.
    """
    predicted = formula_total(record["order_subtotal"], record["discount_applied"])
    assert predicted == pytest.approx(record["total_amount"], abs=0.01)


@pytest.mark.parametrize("record", REAL_DISCOUNTED_RECORDS)
def test_subtraction_formula_does_not_match_real_data(record):
    """Negative control: confirms the brief's literal wording would have
    been wrong, so nobody "fixes" this module back to subtraction later
    without re-deriving why that's incorrect.
    """
    naive_predicted = record["order_subtotal"] - record["discount_applied"]
    assert naive_predicted != pytest.approx(record["total_amount"], abs=0.01)


def test_validate_formula_on_dataframe():
    df = pd.DataFrame(REAL_DISCOUNTED_RECORDS)
    result = validate_formula(df)
    assert result.n_checked == 5
    assert result.match_rate == 1.0


def test_algebraic_solve_recovers_missing_total():
    row = pd.Series({"order_subtotal": 1000.0, "discount_applied": 0.10, "total_amount": None})
    value, field = algebraic_solve(row)
    assert field == "total_amount"
    assert value == pytest.approx(900.0)


def test_algebraic_solve_recovers_missing_subtotal():
    row = pd.Series({"order_subtotal": None, "discount_applied": 0.10, "total_amount": 900.0})
    value, field = algebraic_solve(row)
    assert field == "order_subtotal"
    assert value == pytest.approx(1000.0)


def test_algebraic_solve_zero_discount_is_not_treated_as_missing():
    """discount_applied == 0 is a real value (no discount), not a gap.
    Confirms pd.isna is used, not a falsy check.
    """
    row = pd.Series({"order_subtotal": 500.0, "discount_applied": 0.0, "total_amount": None})
    value, field = algebraic_solve(row)
    assert field == "total_amount"
    assert value == pytest.approx(500.0)


def test_algebraic_solve_returns_none_when_two_fields_missing():
    row = pd.Series({"order_subtotal": None, "discount_applied": None, "total_amount": 500.0})
    value, field = algebraic_solve(row)
    assert value is None
    assert field is None


def test_apply_algebraic_imputation_fills_total_amount():
    df = pd.DataFrame(
        [
            {"order_subtotal": 1000.0, "discount_applied": 0.10, "total_amount": None},
            {"order_subtotal": 500.0, "discount_applied": 0.0, "total_amount": 500.0},
        ]
    )
    result = apply_algebraic_imputation(df)
    assert result.loc[0, "total_amount"] == pytest.approx(900.0)
    assert bool(result.loc[0, "total_amount_imputed"]) == True
    assert result.loc[0, "imputation_method"] == "algebraic"
    assert bool(result.loc[1, "total_amount_imputed"]) == False


def test_sanity_check_flags_implausible_imputed_total():
    df = pd.DataFrame(
        [
            {
                "order_subtotal": 100.0,
                "total_amount": 500.0,  # implausible: exceeds subtotal
                "total_amount_imputed": True,
            }
        ]
    )
    result = sanity_check_imputed(df)
    assert bool(result.loc[0, "imputation_flagged_implausible"]) == True


def test_sanity_check_does_not_flag_non_imputed_rows():
    df = pd.DataFrame(
        [{"order_subtotal": 100.0, "total_amount": 500.0, "total_amount_imputed": False}]
    )
    result = sanity_check_imputed(df)
    assert bool(result.loc[0, "imputation_flagged_implausible"]) == False


def test_sanity_check_catches_implausible_value_even_without_subtotal():
    """Regression test for a real bug found during review: when
    order_subtotal is ALSO missing (the regression-fallback case),
    `total_amount > order_subtotal` evaluates to NaN, which pandas treats
    as falsy -- silently skipping the check on exactly the rows where it
    matters most. Confirms the heuristic fallback (3x branch median) now
    catches this instead of silently passing.
    """
    df = pd.DataFrame(
        [
            {"branch_id": "BR-01", "order_subtotal": 1000.0, "total_amount": 1000.0, "total_amount_imputed": False},
            {"branch_id": "BR-01", "order_subtotal": 1200.0, "total_amount": 1200.0, "total_amount_imputed": False},
            {"branch_id": "BR-01", "order_subtotal": None, "total_amount": 1100.0, "total_amount_imputed": True},
            {"branch_id": "BR-01", "order_subtotal": None, "total_amount": 999999.0, "total_amount_imputed": True},
        ]
    )
    result = sanity_check_imputed(df)
    assert bool(result.loc[2, "imputation_flagged_implausible"]) == False  # sane value, no false positive
    assert bool(result.loc[3, "imputation_flagged_implausible"]) == True   # implausible value, correctly caught


def test_regression_fallback_actually_fires_on_two_missing_fields():
    """Previously the regression path was only proven NOT to crash, never
    proven to produce a sane result on a row with 2+ missing fields (the
    exact case it exists for). This builds enough synthetic training data
    to clear MIN_TRAINING_ROWS and forces a real 2-missing-field row through
    the full algebraic-then-regression pipeline.
    """
    import numpy as np

    rng = np.random.default_rng(42)
    branches = ["BR-01", "BR-02", "BR-03", "BR-04"]
    channels = ["IN_STORE", "ONLINE", "PHONE"]
    methods = ["CASH", "CARD", "TRANSFER"]

    rows = []
    for _ in range(50):
        subtotal = rng.uniform(500, 5000)
        discount = rng.choice([0, 0.1, 0.15, 0.2])
        rows.append(
            {
                "branch_id": rng.choice(branches),
                "order_channel": rng.choice(channels),
                "payment_method": rng.choice(methods),
                "order_items": "burger(x2), coke",
                "order_subtotal": subtotal,
                "discount_applied": discount,
                "total_amount": subtotal * (1 - discount),
            }
        )
    train_df = pd.DataFrame(rows)

    test_row = {
        "branch_id": "BR-02", "order_channel": "ONLINE", "payment_method": "CARD",
        "order_items": "zobo, burger",
        "order_subtotal": None, "discount_applied": None, "total_amount": None,
    }
    df = pd.concat([train_df, pd.DataFrame([test_row])], ignore_index=True)

    df = apply_algebraic_imputation(df)
    assert df["total_amount"].isna().sum() == 1  # algebraic solve can't touch a 2-missing-field row

    model = build_regression_fallback(df)
    assert model is not None  # 50 rows clears MIN_TRAINING_ROWS=30

    df = apply_regression_fallback(df, model)
    assert df["total_amount"].isna().sum() == 0
    assert df.iloc[-1]["imputation_method"] == "regression"
    # sane range check -- training data total_amount maxes out well under 5000
    assert 0 < df.iloc[-1]["total_amount"] < 5000

    df = sanity_check_imputed(df)
    assert bool(df.iloc[-1]["imputation_flagged_implausible"]) == False
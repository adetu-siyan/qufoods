"""
Tests for exploration.profiling.plausibility_checks — covers two gaps found
during review: order_subtotal range sanity (task #10's "check ranges"
requirement, not actually exercised before) and empty order_items on a
COMPLETED sale (a real anomaly that previously passed through silently).
"""

import pandas as pd

from exploration.profiling import plausibility_checks


def _base_sales_df(overrides=None):
    rows = [
        {"transaction_id": f"TXN-{i}", "branch_id": "BR-01", "order_subtotal": 1000.0 + i * 10,
         "order_items": "burger, coke", "transaction_status": "COMPLETED"}
        for i in range(10)
    ]
    if overrides:
        for i, override in overrides.items():
            rows[i].update(override)
    return pd.DataFrame(rows)


def test_flags_non_positive_subtotal():
    df = _base_sales_df({0: {"order_subtotal": 0.0}, 1: {"order_subtotal": -50.0}})
    result = plausibility_checks(df)
    assert result["n_subtotal_anomalies"] == 2
    reasons = set(result["subtotal_anomalies"]["reason"])
    assert reasons == {"non_positive"}


def test_flags_implausibly_large_subtotal():
    # 9 normal rows clustered ~1000-1090, one wild outlier
    df = _base_sales_df({5: {"order_subtotal": 500_000.0}})
    result = plausibility_checks(df)
    assert result["n_subtotal_anomalies"] >= 1
    assert 500_000.0 in result["subtotal_anomalies"]["order_subtotal"].values
    flagged_row = result["subtotal_anomalies"][result["subtotal_anomalies"]["order_subtotal"] == 500_000.0]
    assert flagged_row.iloc[0]["reason"] == "implausibly_large"


def test_does_not_flag_normal_subtotals():
    df = _base_sales_df()
    result = plausibility_checks(df)
    assert result["n_subtotal_anomalies"] == 0


def test_flags_empty_items_on_completed_sale():
    df = _base_sales_df({0: {"order_items": ""}, 1: {"order_items": None}})
    result = plausibility_checks(df)
    assert result["n_empty_items_on_completed_sales"] == 2


def test_does_not_flag_empty_items_on_non_completed_sale():
    """An empty order_items on a FAILED transaction isn't the same anomaly --
    a failed order plausibly never got items attached. Only COMPLETED sales
    with no items is the real red flag.
    """
    df = _base_sales_df({0: {"order_items": "", "transaction_status": "FAILED"}})
    result = plausibility_checks(df)
    assert result["n_empty_items_on_completed_sales"] == 0


def test_does_not_flag_normal_completed_sales():
    df = _base_sales_df()
    result = plausibility_checks(df)
    assert result["n_empty_items_on_completed_sales"] == 0

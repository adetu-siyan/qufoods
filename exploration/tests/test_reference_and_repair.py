"""Tests for exploration.reference and exploration.branch_repair."""

import pandas as pd
import pytest

from exploration.branch_repair import repair_branch_fields
from exploration.reference import FLAGGED_BRANCHES, load_branches, load_menu_items


def test_load_branches_returns_all_20():
    branches = load_branches()
    assert len(branches) == 20
    assert set(branches["branch_id"]) == {f"BR-{i:02d}" for i in range(1, 21)}


def test_every_branch_has_a_region():
    branches = load_branches()
    assert branches["region"].notna().all()
    assert set(branches["region"]) == {"Lagos", "West", "Other"}


def test_lagos_branches_mapped_to_lagos_region():
    branches = load_branches().set_index("branch_id")
    assert branches.loc["BR-01", "region"] == "Lagos"  # Ikeja
    assert branches.loc["BR-02", "region"] == "Lagos"  # Lekki


def test_flagged_branches_match_brief():
    """BR-06/07 = Ogun, BR-15/16/17 = south-east, per the brief."""
    branches = load_branches().set_index("branch_id")
    for bid in FLAGGED_BRANCHES:
        assert bid in branches.index


def test_load_menu_items_returns_13_items():
    items = load_menu_items()
    assert len(items) == 13
    assert "jollof rice" in items


def test_repair_branch_fields_fills_null_branch_name():
    df = pd.DataFrame(
        [{"branch_id": "BR-13", "branch_name": None, "branch_manager": "Blessing Ovwigho"}]
    )
    result = repair_branch_fields(df)
    assert result.loc[0, "branch_name"] == "QuFoods Warri"


def test_repair_branch_fields_warns_on_unknown_branch_id():
    df = pd.DataFrame([{"branch_id": "BR-99", "branch_name": None}])
    with pytest.warns(UserWarning, match="BR-99"):
        repair_branch_fields(df)

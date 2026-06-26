"""
Tests for exploration.cleaning — confirms the 75% rapidfuzz cutoff (see
cleaning.py module docstring for why this overrides the implementation
plan's suggested 85%) correctly catches every real swapped-letter typo
found in the sample batch, and correctly leaves genuinely off-menu items
alone.
"""

import pytest

from exploration.cleaning import clean_order_items, correct_item_name, parse_item_entry

MENU = [
    "jollof rice", "fried rice", "ofada rice", "burger", "chicken wings",
    "grilled fish", "plantain", "coleslaw", "puff puff", "coke", "zobo",
    "water", "chapman",
]

# Real typos observed in the sample batch — these MUST be auto-corrected.
REAL_TYPOS = [
    ("ocke", "coke"),
    ("ckoe", "coke"),
    ("chickne wings", "chicken wings"),
    ("ofada irce", "ofada rice"),
    ("chicekn wings", "chicken wings"),
]


@pytest.mark.parametrize("typo,expected", REAL_TYPOS)
def test_real_typos_are_corrected_at_75_cutoff(typo, expected):
    corrected, changed, score = correct_item_name(typo, MENU, cutoff=75.0)
    assert corrected == expected
    assert changed is True
    assert score >= 75.0


def test_off_menu_item_is_left_unchanged():
    """spaghetti carbonara isn't a typo of anything on the menu - must not
    be force-matched to something just because it's the closest option.
    """
    corrected, changed, score = correct_item_name("spaghetti carbonara", MENU, cutoff=75.0)
    assert changed is False
    assert corrected == "spaghetti carbonara"


def test_exact_match_is_not_flagged_as_a_correction():
    corrected, changed, score = correct_item_name("jollof rice", MENU)
    assert corrected == "jollof rice"
    assert changed is False
    assert score == 100.0


def test_parse_item_entry_extracts_quantity():
    name, qty = parse_item_entry("burger(x2)")
    assert name == "burger"
    assert qty == 2


def test_parse_item_entry_defaults_quantity_to_one():
    name, qty = parse_item_entry("zobo")
    assert name == "zobo"
    assert qty == 1


def test_clean_order_items_fixes_multi_item_string():
    raw = "ofada irce, zobo(x2), coke(x2), grilled fish"
    cleaned, had_correction, detail = clean_order_items(raw, MENU, cutoff=75.0)
    assert "ofada rice" in cleaned
    assert had_correction is True
    assert any(d["original"] == "ofada irce" and d["changed"] for d in detail)


def test_clean_order_items_preserves_quantities():
    raw = "burger(x2), chicekn wings"
    cleaned, _, _ = clean_order_items(raw, MENU, cutoff=75.0)
    assert "burger(x2)" in cleaned
    assert "chicken wings" in cleaned

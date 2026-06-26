"""
exploration.reference
======================

Loads the canonical reference data — branch registry and menu item list —
and derives the region mapping (Lagos / West / Other) that the brief and
reporting layer both need.

Single source of truth: every other module (cleaning, imputation, reporting)
should import from here rather than hardcoding branch or item lists. If
QuFoods opens branch 21 next quarter, this is the only place that needs to
change.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"

# Region mapping is a business decision, not something derivable purely from
# the `state` column — "West" here means the wider western Nigeria cluster
# beyond Lagos itself (Oyo, Ogun, Ondo, Osun), distinct from Lagos state and
# from "Other" (FCT, south-south, south-east, north). Lock this here once and
# everyone downstream (Bukolami's schema, Daniel's regional reports) uses the
# same definition.
STATE_TO_REGION = {
    "Lagos": "Lagos",
    "Oyo": "West",
    "Ogun": "West",
    "Ondo": "West",
    "Osun": "West",
    "FCT": "Other",
    "Rivers": "Other",
    "Delta": "Other",
    "Edo": "Other",
    "Enugu": "Other",
    "Anambra": "Other",
    "Abia": "Other",
    "Kaduna": "Other",
    "Kano": "Other",
    "Plateau": "Other",
}

# Branches the brief specifically flags as having known data-quality issues.
# BR-06/BR-07 = Ogun State; BR-15/BR-16/BR-17 = south-east cluster.
FLAGGED_BRANCHES = ["BR-06", "BR-07", "BR-15", "BR-16", "BR-17"]


def load_branches(reference_dir: str | Path = DEFAULT_REFERENCE_DIR) -> pd.DataFrame:
    """Load the canonical branch registry and attach the region mapping."""
    path = Path(reference_dir) / "reference_branches.csv"
    branches = pd.read_csv(path)

    unmapped = set(branches["state"]) - set(STATE_TO_REGION)
    if unmapped:
        raise ValueError(
            f"States in reference_branches.csv with no region mapping: {unmapped}. "
            "Update STATE_TO_REGION in exploration/src/exploration/reference.py."
        )

    branches["region"] = branches["state"].map(STATE_TO_REGION)
    return branches


def load_menu_items(reference_dir: str | Path = DEFAULT_REFERENCE_DIR) -> list[str]:
    """Load the canonical (lowercased) menu item list used for fuzzy matching."""
    path = Path(reference_dir) / "reference_menu_items.csv"
    menu = pd.read_csv(path)
    return menu["item_name"].str.lower().str.strip().tolist()


def branch_lookup(reference_dir: str | Path = DEFAULT_REFERENCE_DIR) -> pd.DataFrame:
    """Branch registry indexed by branch_id — convenient for `.map()` repairs."""
    return load_branches(reference_dir).set_index("branch_id")

"""
exploration.cleaning
=====================

Implements Implementation Plan tasks #14-15:
  14. Fix misspelled item names using rapidfuzz against the reference menu list
  15. Set confidence threshold for auto-correction (85% suggested)

The starter notebook proves out the *mechanics* of typo correction using
`difflib` at a 60% cutoff. This module upgrades that to `rapidfuzz` (faster,
and the library the brief explicitly hints at) and raises the threshold to
85, per the implementation plan. The function signatures intentionally
mirror the starter notebook's (`split_order_items`, `parse_item_entry`,
`clean_order_items`) so this is a drop-in upgrade, not a rewrite — anyone
who already read the starter notebook can read this in five minutes.

WHY 75 AND NOT THE PLAN'S SUGGESTED 85
----------------------------------------
The implementation plan suggested 85 as a starting point, but checking it
against the actual typos in the sample batch shows 85 is too conservative
and would silently FAIL to auto-correct real, obvious typos. Short item
names lose more similarity percentage per swapped letter than long ones:

    "ocke"          vs "coke"           -> 75.0  (4-letter swap)
    "ckoe"          vs "coke"           -> 75.0  (4-letter swap)
    "chickne wings" vs "chicken wings"  -> 92.3  (13-letter swap)
    "ofada irce"    vs "ofada rice"     -> 90.0  (10-letter swap)
    "chicekn wings" vs "chicken wings"  -> 92.3  (13-letter swap)

At cutoff=85, "ocke" and "ckoe" would NOT be corrected — exactly the kind
of silent failure the brief warns against. Checking the other direction —
whether a lower cutoff risks false-matching something genuinely off-menu —
the highest score any real off-menu Nigerian dish gets against this 13-item
menu is 50 ("amala" vs "chapman"; everything else scores lower). That
leaves a wide, evidence-backed gap between 50 and 75 with nothing observed
in between, so 75 is set as the cutoff: low enough to catch every real
typo found, high enough to leave clear headroom above the off-menu cluster.
This reasoning is logged as Data Quality Log Finding #3 (see HANDOFF.md /
DATA_QUALITY_LOG.md) since it overrides the plan's own suggested value —
worth flagging explicitly to the team rather than changing it silently.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

_QTY_RE = re.compile(r"^(?P<name>.+?)\(x(?P<qty>\d+)\)$", re.IGNORECASE)

TYPO_MATCH_CUTOFF = 75.0  # rapidfuzz score is 0-100, not 0-1 like difflib's ratio() -- see module docstring for why 75, not the plan's suggested 85


def split_order_items(raw: object) -> list[str]:
    """Split the free-text `order_items` field on commas.

    Identical to the starter notebook's function — kept here so the whole
    cleaning pipeline lives in one importable module instead of being split
    across a notebook and a package.
    """
    if raw is None or (isinstance(raw, float) and raw != raw):  # NaN check w/o pandas dep
        return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def parse_item_entry(entry: str) -> tuple[str, int]:
    """Split an entry like 'burger(x2)' into ('burger', 2); ('zobo', 1) if no qty."""
    match = _QTY_RE.match(entry)
    if match:
        return match.group("name").strip(), int(match.group("qty"))
    return entry.strip(), 1


def score_candidates(name: str, reference_items_lower: list[str]) -> list[tuple[str, float]]:
    """Similarity of `name` against every canonical menu item, for inspection.

    Returns (item, score) pairs sorted best-first, score 0-100.
    """
    name_lower = name.lower()
    results = process.extract(
        name_lower, reference_items_lower, scorer=fuzz.ratio, limit=len(reference_items_lower)
    )
    # rapidfuzz returns (choice, score, index); drop the index, keep what we need
    return [(choice, round(score, 1)) for choice, score, _ in results]


def correct_item_name(
    name: str,
    reference_items_lower: list[str],
    cutoff: float = TYPO_MATCH_CUTOFF,
) -> tuple[str, bool, float]:
    """Return (corrected_name, was_changed, match_score).

    Exact matches short-circuit with score 100 and `was_changed=False` —
    matching the starter notebook's behavior of not treating an exact hit
    as a "correction."

    Below `cutoff`, the name is returned unchanged and unflagged-as-fixed —
    deliberately. Forcing a low-confidence substitution would silently
    corrupt the record; better to leave it for a human to review (this
    shows up downstream as an item that doesn't appear in the canonical
    menu — see the data quality log, Finding #2 sub-case).
    """
    name_lower = name.lower()
    if name_lower in reference_items_lower:
        return name_lower, False, 100.0

    match = process.extractOne(name_lower, reference_items_lower, scorer=fuzz.ratio)
    if match is None:
        return name_lower, False, 0.0

    choice, score, _ = match
    if score >= cutoff:
        return choice, True, round(score, 1)
    return name_lower, False, round(score, 1)


def clean_order_items(
    raw: object,
    reference_items_lower: list[str],
    cutoff: float = TYPO_MATCH_CUTOFF,
) -> tuple[str, bool, list[dict]]:
    """Clean every item in a raw `order_items` string.

    Returns (cleaned_string, had_any_correction, correction_detail) where
    correction_detail is a list of per-item dicts — useful for building the
    "what got changed and why" audit trail Emmanuel's Lambda will want to
    log per-record, not just a boolean.
    """
    had_correction = False
    cleaned_parts = []
    detail = []

    for entry in split_order_items(raw):
        name, qty = parse_item_entry(entry)
        corrected, changed, score = correct_item_name(name, reference_items_lower, cutoff)
        had_correction = had_correction or changed
        cleaned_parts.append(f"{corrected}(x{qty})" if qty > 1 else corrected)
        detail.append(
            {
                "original": name,
                "corrected": corrected,
                "changed": changed,
                "match_score": score,
                "on_menu_after_correction": corrected in reference_items_lower,
            }
        )

    return ", ".join(cleaned_parts), had_correction, detail

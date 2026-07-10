"""QuFoods exploration package.

Public API — the functions Emmanuel, Bukolami, and Daniel are most likely
to need directly:

    from exploration.pipeline import run
    from exploration.cleaning import clean_order_items, TYPO_MATCH_CUTOFF
    from exploration.imputation import formula_total, algebraic_solve
    from exploration.reference import load_branches, load_menu_items, STATE_TO_REGION

See HANDOFF.md at the repo root of this folder for the full contract.
"""

from exploration.pipeline import PipelineResult, run  # noqa: F401

__all__ = ["run", "PipelineResult"]

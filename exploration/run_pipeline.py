import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from exploration.pipeline import run

print("Running QuFoods cleaning pipeline...")
result = run(use_s3=False, sample_dir="data/sample_batches")

print("Done.")
print(f"  raw records:           {result.raw_record_count}")
print(f"  sales records:         {len(result.sales_df)}")
print(f"  expense records:       {len(result.expense_df)}")
print(f"  typo corrections:      {result.n_typo_corrections}")
print(f"  totals imputed:        {result.n_algebraic_imputations}")
print(f"  formula match rate:    {result.formula_validation.match_rate:.1%}")
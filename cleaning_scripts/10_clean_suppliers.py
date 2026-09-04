"""
Cleaning script for suppliers.csv

Issues found (see docs/CLEANING_LOG.md for the full investigation -- this table was
straightforward, matching patterns already established on earlier tables):
1. region: case + whitespace inconsistency, no exceptions this time.
2. contract_start_date: mixed date string formats (familiar pattern).
3. payment_terms_days: 5 missing values, no explanatory pattern found -> left untouched.

Input:  raw suppliers.csv (from the acpl-synthetic-dataset repo)
Output: data/suppliers.csv (cleaned)
"""
import pandas as pd

RAW_PATH = "../acpl-synthetic-dataset/data/suppliers.csv"  # adjust to your local path
OUTPUT_PATH = "../data/suppliers.csv"


def main():
    df = pd.read_csv(RAW_PATH)
    before_shape = df.shape

    # Fix 1: region case + whitespace. No brand-name-style exceptions this time.
    df["region"] = df["region"].str.strip().str.title()

    # Fix 2: mixed date formats -> real datetime type.
    df["contract_start_date"] = pd.to_datetime(df["contract_start_date"], format="mixed", dayfirst=True, errors="coerce")

    # payment_terms_days missing (5) intentionally left as-is -- no explanatory
    # pattern found across region, contract age, or base_lead_time_days.

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Before: {before_shape} -> After: {df.shape}")
    print(f"Saved -> {OUTPUT_PATH}")
    print(f"region unique values: {df['region'].unique()}")
    print(f"contract_start_date dtype: {df['contract_start_date'].dtype}")
    print(f"payment_terms_days missing: {df['payment_terms_days'].isna().sum()}")


if __name__ == "__main__":
    main()

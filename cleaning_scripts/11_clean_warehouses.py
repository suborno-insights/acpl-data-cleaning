"""
Cleaning script for warehouses.csv (last table in the series)

Issues found (see docs/CLEANING_LOG.md for the full investigation, and a series
summary across all 11 tables at the end of that file):
1. operational_since: mixed date string formats (familiar pattern).
2. capacity_units: 1 of 3 rows missing, no recoverable signal (only 3 warehouses
   total -- no time-series to interpolate, no related column gives a numeric
   hint) -> left untouched.

Input:  raw warehouses.csv (from the acpl-synthetic-dataset repo)
Output: data/warehouses.csv (cleaned)
"""
import pandas as pd

RAW_PATH = "../acpl-synthetic-dataset/data/warehouses.csv"  # adjust to your local path
OUTPUT_PATH = "../data/warehouses.csv"


def main():
    df = pd.read_csv(RAW_PATH)
    before_shape = df.shape

    # Fix: mixed date formats -> real datetime type.
    df["operational_since"] = pd.to_datetime(df["operational_since"], format="mixed", dayfirst=True, errors="coerce")

    # capacity_units missing (1 of 3) intentionally left as-is -- no recoverable
    # signal exists in a 3-row table with no related time-series or numeric hint.

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Before: {before_shape} -> After: {df.shape}")
    print(f"Saved -> {OUTPUT_PATH}")
    print(f"operational_since dtype: {df['operational_since'].dtype}")
    print(f"capacity_units missing: {df['capacity_units'].isna().sum()}")


if __name__ == "__main__":
    main()

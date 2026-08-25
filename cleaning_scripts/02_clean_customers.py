"""
Cleaning script for customers.csv

Issues found (see docs/CLEANING_LOG.md for the full investigation, including 2 false
positives caught and corrected before trusting them):
1. join_date: 3 mixed date string formats (DD/MM/YYYY, YYYY-MM-DD, Month D, YYYY)
2. region: case + whitespace inconsistency (24 raw variants of 6 real regions)
3. region: 446 missing values, left untouched by design (a downstream decision)
4. 40 fully duplicate rows

Input:  raw customers.csv (from the acpl-synthetic-dataset repo)
Output: data/customers.csv (cleaned)
"""
import pandas as pd

RAW_PATH = "../acpl-synthetic-dataset/data/customers.csv"  # adjust to your local path
OUTPUT_PATH = "../data/customers.csv"


def main():
    df = pd.read_csv(RAW_PATH)
    before_shape = df.shape

    # Fix 1: mixed date formats -> real datetime type.
    # dayfirst=True matters: without it, ambiguous DD/MM/YYYY (day<=12) values get
    # silently misread as MM/DD/YYYY.
    df["join_date"] = pd.to_datetime(df["join_date"], format="mixed", dayfirst=True, errors="coerce")

    # Fix 2: region case/whitespace inconsistency. No brand-name-style exceptions
    # here (unlike carrier_name), so the generic method is safe as-is.
    # NaN passes through .str methods untouched -- verified, missing count unchanged.
    df["region"] = df["region"].str.strip().str.title()

    # region missing values (446) intentionally left as-is -- see CLEANING_LOG.md

    # Fix 3: drop fully duplicate rows
    df = df.drop_duplicates()

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Before: {before_shape} -> After: {df.shape}")
    print(f"Saved -> {OUTPUT_PATH}")
    print(f"join_date dtype: {df['join_date'].dtype}")
    print(f"region unique values: {df['region'].unique()}")
    print(f"region missing count: {df['region'].isna().sum()}")


if __name__ == "__main__":
    main()

"""
Cleaning script for stores.csv

Issues found (see docs/CLEANING_LOG.md for the full investigation):
1. city: case + whitespace inconsistency, with an apostrophe exception
   ("Cox's Bazar" -> generic .title() breaks it into "Cox'S Bazar" -- tested on a
   sample first, then applied generic fix + targeted override for this one value).
2. opening_date: mixed date string formats (familiar pattern).
3. store_id: 1 fully identical duplicate row (ST03) -> removed.
4. manager_name: 1 missing value, no explanatory pattern found -> left untouched.

Input:  raw stores.csv (from the acpl-synthetic-dataset repo)
Output: data/stores.csv (cleaned)
"""
import pandas as pd

RAW_PATH = "../acpl-synthetic-dataset/data/stores.csv"  # adjust to your local path
OUTPUT_PATH = "../data/stores.csv"


def main():
    df = pd.read_csv(RAW_PATH)
    before_shape = df.shape

    # Fix 1: city case + whitespace, with a targeted override for the apostrophe case.
    df["city"] = df["city"].str.strip().str.title()
    df["city"] = df["city"].replace("Cox'S Bazar", "Cox's Bazar")

    # Fix 2: mixed date formats -> real datetime type.
    df["opening_date"] = pd.to_datetime(df["opening_date"], format="mixed", dayfirst=True, errors="coerce")

    # Fix 3: exact duplicate row.
    df = df.drop_duplicates(subset=["store_id"], keep="first")

    # manager_name missing (1) intentionally left as-is -- no explanatory pattern found.

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Before: {before_shape} -> After: {df.shape}")
    print(f"Saved -> {OUTPUT_PATH}")
    print(f"city unique values: {df['city'].unique()}")
    print(f"opening_date dtype: {df['opening_date'].dtype}")
    print(f"store_id duplicates remaining: {df.duplicated(subset=['store_id']).sum()}")
    print(f"manager_name missing: {df['manager_name'].isna().sum()}")


if __name__ == "__main__":
    main()

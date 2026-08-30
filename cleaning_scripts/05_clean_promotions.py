"""
Cleaning script for promotions.csv

Issues found (see docs/CLEANING_LOG.md for the full investigation):
1. start_date/end_date: mixed date string formats, mislabeled "Mixed Case Styles"
   by the generic text checker (same root cause as customers.join_date and
   inventory_snapshots.snapshot_date).
2. channel: case + whitespace inconsistency (10 raw variants -> 3 clean values).
   Verified the hyphen in "In-store" doesn't break .str.title() the way it broke
   detection on acquisition_channel's "Walk-in" (detection bug != fixing bug).
3. discount_pct: 12 missing values, left untouched by design -- checked for
   contradiction against other columns (found none, unlike stock_qty vs
   stockout_flag) and confirmed this is a plausible real-world scenario (not
   every promotion needs a percentage discount, e.g. BOGO-style deals).
4. product_id "duplicate" flag was a false positive (a product can legitimately
   run multiple promotions over time -- one row per promotion event, not per product).

Input:  raw promotions.csv (from the acpl-synthetic-dataset repo)
Output: data/promotions.csv (cleaned)
"""
import pandas as pd

RAW_PATH = "../acpl-synthetic-dataset/data/promotions.csv"  # adjust to your local path
OUTPUT_PATH = "../data/promotions.csv"


def main():
    df = pd.read_csv(RAW_PATH)
    before_shape = df.shape

    # Fix 1: mixed date formats -> real datetime type (dayfirst=True, same reasoning
    # as every other date column in this dataset).
    df["start_date"] = pd.to_datetime(df["start_date"], format="mixed", dayfirst=True, errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], format="mixed", dayfirst=True, errors="coerce")

    # Fix 2: channel case + whitespace inconsistency. No brand-name-style
    # exceptions here -- verified the hyphen in "In-store" survives .str.title()
    # correctly (unlike .istitle() used for detection, which does break on hyphens).
    df["channel"] = df["channel"].str.strip().str.title()

    # discount_pct missing values (12) intentionally left as-is -- checked for
    # contradiction against other columns in the same rows (start_date, end_date,
    # campaign_name, channel all present and consistent) and concluded this is a
    # plausible real scenario, not an error -- see CLEANING_LOG.md

    # product_id "duplicate" flag from investigate.py is a false positive for this
    # table (one row per promotion event; a product can have multiple promotions
    # over time) -- no action needed.

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Before: {before_shape} -> After: {df.shape}")
    print(f"Saved -> {OUTPUT_PATH}")
    print(f"start_date/end_date dtypes: {df['start_date'].dtype}, {df['end_date'].dtype}")
    print(f"channel unique values: {df['channel'].unique()}")
    print(f"discount_pct missing (left as-is): {df['discount_pct'].isna().sum()}")


if __name__ == "__main__":
    main()

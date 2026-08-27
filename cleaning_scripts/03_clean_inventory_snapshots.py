"""
Cleaning script for inventory_snapshots.csv

Issues found (see docs/CLEANING_LOG.md for the full investigation, including 2 false
positives and one genuine logical-inconsistency finding):
1. stock_qty: 115 negative values (sign-flip error, confirmed via magnitude comparison)
2. stock_qty: 3,279 missing values, WITH a logical inconsistency against stockout_flag
   (unlike customers.region, "leave it untouched" was not an acceptable choice here)
3. snapshot_date: 3 mixed date string formats (only visible via .sample(), not .head())
4. product_id/warehouse_id "duplicate" flags were false positives (this table's real
   grain is the composite key product_id+warehouse_id+snapshot_date)

Input:  raw inventory_snapshots.csv (from the acpl-synthetic-dataset repo)
Output: data/inventory_snapshots.csv (cleaned)
"""
import pandas as pd

RAW_PATH = "../acpl-synthetic-dataset/data/inventory_snapshots.csv"  # adjust to your local path
OUTPUT_PATH = "../data/inventory_snapshots.csv"


def main():
    df = pd.read_csv(RAW_PATH)
    before_shape = df.shape

    # Fix 1: negative stock_qty -> sign-flip error, magnitude distribution matched
    # normal positive values, so .abs() is a justified fix (not fabricating data).
    df["stock_qty"] = df["stock_qty"].abs()

    # Fix 2: mixed date formats -> real datetime type (dayfirst=True for the same
    # DD/MM/YYYY ambiguity reason as customers.join_date).
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], format="mixed", dayfirst=True, errors="coerce")

    # Fix 3: missing stock_qty. Time-series data (per product+warehouse) supports
    # interpolation, unlike a static category like customers.region.
    df = df.sort_values(["product_id", "warehouse_id", "snapshot_date"])
    df["stock_qty_was_missing"] = df["stock_qty"].isna()  # keep the observed-vs-estimated distinction
    df["stock_qty"] = df.groupby(["product_id", "warehouse_id"])["stock_qty"].transform(
        lambda x: x.interpolate(method="linear", limit_direction="both")
    )

    # product_id / warehouse_id "duplicate" flags from investigate.py are false positives
    # for this table (grain is product+warehouse+date, not a single ID) -- no action needed.

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Before: {before_shape} -> After: {df.shape}")
    print(f"Saved -> {OUTPUT_PATH}")
    print(f"Negative stock_qty remaining: {(df['stock_qty'] < 0).sum()}")
    print(f"Missing stock_qty remaining: {df['stock_qty'].isna().sum()}")
    print(f"snapshot_date dtype: {df['snapshot_date'].dtype}")
    print(f"Composite-key duplicates: {df.duplicated(subset=['product_id','warehouse_id','snapshot_date']).sum()}")


if __name__ == "__main__":
    main()

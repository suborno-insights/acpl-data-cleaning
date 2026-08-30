"""
Cleaning script for products.csv

Issues found (see docs/CLEANING_LOG.md for the full investigation):
1. unit_price: entire column was object dtype due to a currency symbol (৳) in some
   values -- invisible to investigate.py's numeric-anomaly check, which only looks
   at columns pandas already recognizes as numeric.
2. unit_price: 1 value was exactly 0 (business-logic impossible) -> set to NaN
   (unverifiable what the real price was; not fabricated).
3. category: case + whitespace inconsistency (26 raw variants -> 8 clean values).
4. unit_cost: 1 negative value (-107.05) -> verified via margin-% consistency check
   against other products, then .abs()'d (a mathematically certain fix).
5. unit_cost: 1 extreme outlier (4206.70, ~10x plausible) -> set to NaN rather than
   guessing "divide by 10" (an unverifiable guess, unlike the sign-flip case).
6. 1 fully duplicate row (product_id P006) -> removed.

Input:  raw products.csv (from the acpl-synthetic-dataset repo)
Output: data/products.csv (cleaned)
"""
import pandas as pd

RAW_PATH = "../acpl-synthetic-dataset/data/products.csv"  # adjust to your local path
OUTPUT_PATH = "../data/products.csv"


def main():
    df = pd.read_csv(RAW_PATH)
    before_shape = df.shape

    # Fix 1: unit_price stored as text due to a ৳ symbol on some rows.
    df["unit_price"] = df["unit_price"].str.replace("৳", "", regex=False)
    df["unit_price"] = pd.to_numeric(df["unit_price"])

    # Fix 2: unit_price == 0 is a business-logic violation (no product is free),
    # and not explainable by is_active/unit_cost context. No verifiable way to
    # recover the real price -> NaN, not a guess.
    df.loc[df["unit_price"] == 0, "unit_price"] = pd.NA

    # Fix 3: category case + whitespace inconsistency. No brand-name-style
    # exceptions here, so the generic method is safe as-is.
    df["category"] = df["category"].str.strip().str.title()

    # Fix 4: unit_cost negative value -- verified via margin-% consistency check
    # (P046's implied margin, treating cost as positive, matched the normal range
    # seen across other products) before applying .abs().
    df["unit_cost"] = df["unit_cost"].abs()

    # Fix 5: unit_cost extreme outlier (P180, ~10x a plausible value). Unlike the
    # sign-flip case, "divide by 10" is a guess with no mathematical certainty
    # behind it -> NaN, not a fabricated correction.
    df.loc[df["product_id"] == "P180", "unit_cost"] = pd.NA

    # Fix 6: exact duplicate row on the real primary key.
    df = df.drop_duplicates(subset=["product_id"], keep="first")

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Before: {before_shape} -> After: {df.shape}")
    print(f"Saved -> {OUTPUT_PATH}")
    print(f"unit_price dtype: {df['unit_price'].dtype}")
    print(f"unit_cost missing: {df['unit_cost'].isna().sum()} | unit_price missing: {df['unit_price'].isna().sum()}")
    print(f"Negative unit_cost remaining: {(df['unit_cost'] < 0).sum()}")
    print(f"category unique values: {df['category'].nunique()}")
    print(f"Duplicate product_id remaining: {df.duplicated(subset=['product_id']).sum()}")


if __name__ == "__main__":
    main()

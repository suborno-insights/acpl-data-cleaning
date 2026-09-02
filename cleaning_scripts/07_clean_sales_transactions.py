"""
Cleaning script for sales_transactions.csv (the largest table, ~290,700 rows)

Issues found (see docs/CLEANING_LOG.md for the full investigation -- this table
combined nearly every pattern learned on earlier tables, plus two new ones):
1. transaction_date: mixed date formats.
2. store_id: case+whitespace (fixed with .upper(), not .title() -- it's an ID/code).
3. payment_method: case+whitespace AND placeholder values ('Unknown', '-') unified
   with real NaN before fixing case.
4. transaction_id: 2,306 real duplicates, only detectable after fixing BOTH
   transaction_date AND payment_method first (two prerequisite columns, not one).
5. unit_price == 0 (287 rows): recovery formula (total_amount/quantity) only held
   cleanly for 257 of 287 rows (zero-discount ones) -> treated the whole group as
   unrecovered rather than splitting into two different fixes -> NaN.
6. quantity: 290 negative values, verified via magnitude comparison -> .abs().
7. promo_id missing (98.27%): verified as the expected normal case (few short
   promo campaigns vs. 2 years of transactions), not a defect -- left untouched.
8. discount_pct missing (19,869): PROVEN from data that no-promo transactions
   have discount_pct==0 and promo transactions always have a real percentage ->
   filled the no-promo subset with 0 (a data-verified fill, not a guess). The
   remaining 350 rows (promo_id present but discount_pct still missing) are a
   genuine contradiction with no recoverable value -> left as NaN, documented as
   a landmine (do not blanket-fillna(0) this column in any later step).
9. customer_id missing (14,512 after dedup): no clean explanation found (not
   concentrated in one payment_method) -> left untouched, with the downstream
   impact on customer-level analysis (e.g. Project 6 RFM) explicitly documented.

Input:  raw sales_transactions.csv (from the acpl-synthetic-dataset repo)
Output: data/sales_transactions.csv (cleaned)
"""
import pandas as pd

RAW_PATH = "../acpl-synthetic-dataset/data/sales_transactions.csv"  # adjust to your local path
OUTPUT_PATH = "../data/sales_transactions.csv"


def main():
    df = pd.read_csv(RAW_PATH)
    before_shape = df.shape

    # Fix 1: mixed date formats -> real datetime type. Must happen before the
    # transaction_id duplicate check below.
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], format="mixed", dayfirst=True, errors="coerce")

    # Fix 2: store_id case+whitespace. .upper() (not .title()) -- it's an ID/code.
    df["store_id"] = df["store_id"].str.strip().str.upper()

    # Fix 3: payment_method placeholders unified with real NaN, then case fixed.
    # This must also happen before the transaction_id duplicate check below --
    # duplicate pairs differed by payment_method casing as well as date format.
    df["payment_method"] = df["payment_method"].replace(["Unknown", "-"], pd.NA)
    df["payment_method"] = df["payment_method"].str.strip().str.title()

    # Fix 4: transaction_id duplicates, now correctly detectable post date+payment fix.
    df = df.drop_duplicates(subset=["transaction_id"], keep="first")

    # Fix 5: unit_price == 0. Recovery formula only held cleanly for a subset
    # (zero-discount rows); rather than split into two fixes, treat the whole
    # group as unrecovered.
    df.loc[df["unit_price"] == 0, "unit_price"] = pd.NA

    # Fix 6: quantity negative values -- verified via magnitude comparison.
    df["quantity"] = df["quantity"].abs()

    # promo_id missing (98.27%) intentionally left as-is -- verified to be the
    # expected normal case, not a defect.

    # Fix 7: discount_pct -- data-verified fill, scoped ONLY to no-promo rows.
    # Rows WITH a promo_id but missing discount_pct (a genuine contradiction,
    # ~350 rows) are intentionally left as NaN -- do not extend this fillna to
    # the whole column in any future step.
    df.loc[df["promo_id"].isna(), "discount_pct"] = df.loc[df["promo_id"].isna(), "discount_pct"].fillna(0)

    # customer_id missing (~14,500 rows) intentionally left as-is -- no clean
    # explanation found. See CLEANING_LOG.md for the downstream analysis impact.

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Before: {before_shape} -> After: {df.shape}")
    print(f"Saved -> {OUTPUT_PATH}")
    print(f"transaction_id duplicates remaining: {df.duplicated(subset=['transaction_id']).sum()}")
    print(f"Negative quantity remaining: {(df['quantity'] < 0).sum()}")
    print(f"unit_price == 0 remaining: {(df['unit_price'] == 0).sum()}")
    print(f"discount_pct missing (should be ~350, promo_id present but no discount): {df['discount_pct'].isna().sum()}")
    print(f"customer_id missing (left untouched): {df['customer_id'].isna().sum()}")


if __name__ == "__main__":
    main()

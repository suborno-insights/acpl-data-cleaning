"""
Cleaning script for purchase_orders.csv

Issues found (see docs/CLEANING_LOG.md for the full investigation -- this table had
the most involved findings so far):
1. order_date/expected_delivery_date/actual_delivery_date: mixed date string formats
   (mislabeled "Mixed Case Styles" by the generic text checker).
2. po_id: 140 REAL duplicates, only detectable AFTER fixing the date columns above --
   duplicate pairs were identical in every column except date representation
   (e.g. '22/11/2024' vs 'November 22, 2024' -- same date, different string).
3. actual_delivery_date: 365 missing values, verified consistent with po_status
   == 'Pending' (a delivery that hasn't happened has no delivery date -- correct
   state, not missing data) -- left untouched.
4. order_qty: 77 negative values, verified via magnitude comparison against normal
   positive values (consistent with a sign-flip error) -> .abs().
5. Cross-column inconsistency: order_qty vs qty_received + qty_rejected don't add
   up for 2,230 rows (333 genuine arithmetic mismatches + ~1,905 rows where
   qty_rejected is simply missing). No fixable answer exists for either case --
   flagged in a new qty_mismatch_flag column rather than guessed at or deleted.
6. rejection_reason: case + whitespace inconsistency (16 variants -> 4 clean values).

Input:  raw purchase_orders.csv (from the acpl-synthetic-dataset repo)
Output: data/purchase_orders.csv (cleaned)
"""
import pandas as pd

RAW_PATH = "../acpl-synthetic-dataset/data/purchase_orders.csv"  # adjust to your local path
OUTPUT_PATH = "../data/purchase_orders.csv"


def main():
    df = pd.read_csv(RAW_PATH)
    before_shape = df.shape

    # Fix 1: mixed date formats -> real datetime type. This must happen BEFORE the
    # po_id duplicate check below -- duplicate rows are only detectable as
    # string-identical once date representations are normalized.
    df["order_date"] = pd.to_datetime(df["order_date"], format="mixed", dayfirst=True, errors="coerce")
    df["expected_delivery_date"] = pd.to_datetime(df["expected_delivery_date"], format="mixed", dayfirst=True, errors="coerce")
    df["actual_delivery_date"] = pd.to_datetime(df["actual_delivery_date"], format="mixed", dayfirst=True, errors="coerce")

    # Fix 2: po_id duplicates, now correctly detectable post date-fix.
    df = df.drop_duplicates(subset=["po_id"], keep="first")

    # actual_delivery_date missing (365) intentionally left as-is -- verified
    # 100% consistent with po_status == 'Pending' (order hasn't been delivered yet).

    # Fix 3: order_qty negative values -- verified via magnitude comparison
    # (matched the normal positive distribution), consistent with a sign-flip error.
    df["order_qty"] = df["order_qty"].abs()

    # Fix 4: cross-column quantity inconsistency. No verifiable correction exists
    # for either root cause (arithmetic mismatch or missing qty_rejected) -- flag
    # rather than guess, delete, or leave looking trustworthy.
    df["qty_mismatch_flag"] = False
    df.loc[
        (df["qty_rejected"].notna()) & (df["qty_received"] + df["qty_rejected"] != df["order_qty"]),
        "qty_mismatch_flag",
    ] = True
    df.loc[df["qty_rejected"].isna(), "qty_mismatch_flag"] = True

    # Fix 5: rejection_reason case + whitespace inconsistency.
    df["rejection_reason"] = df["rejection_reason"].str.strip().str.title()

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Before: {before_shape} -> After: {df.shape}")
    print(f"Saved -> {OUTPUT_PATH}")
    print(f"po_id duplicates remaining: {df.duplicated(subset=['po_id']).sum()}")
    print(f"Negative order_qty remaining: {(df['order_qty'] < 0).sum()}")
    print(f"qty_mismatch_flag counts:\n{df['qty_mismatch_flag'].value_counts()}")
    print(f"rejection_reason unique values: {df['rejection_reason'].unique()}")


if __name__ == "__main__":
    main()

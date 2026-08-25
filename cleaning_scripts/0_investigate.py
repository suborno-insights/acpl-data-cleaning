"""
Reusable data-quality investigation script.

This is the generalized version of the audit process worked out on carriers.csv
(see docs/CLEANING_LOG.md for how the text/category-inconsistency check evolved
through two failed attempts before landing on the per-value case-style check below).

Usage:
    python investigate.py path/to/table.csv
or import and call investigate(df) directly on a DataFrame.
"""
import sys
import pandas as pd


def investigate(df: pd.DataFrame, table_name: str = "table"):
    print("=" * 60)
    print(f" DATA QUALITY INVESTIGATION REPORT — {table_name}")
    print("=" * 60)

    # 1. Basic structure
    print("\n--- [1] BASIC STRUCTURE ---")
    print(f"Total Rows: {len(df)} | Total Columns: {len(df.columns)}")
    print(df.dtypes)

    # 2. Missing values
    print("\n--- [2] MISSING VALUES ---")
    missing = df.isnull().sum()
    missing_pct = (df.isnull().mean() * 100).round(2)
    missing_report = pd.DataFrame({"Missing Count": missing, "Percentage (%)": missing_pct})
    print(missing_report[missing_report["Missing Count"] > 0])
    if missing_report["Missing Count"].sum() == 0:
        print("No missing values (NaN) found.")

    # 2b. Hidden placeholder-style values in text columns (e.g. "N/A", "Unknown", "-")
    placeholder_tokens = {"n/a", "na", "unknown", "-", "none", "null", "tbd", ""}
    print("\n[Possible Hidden Placeholders]:")
    found_placeholder = False
    for col in df.select_dtypes(include=["object"]):
        vals = df[col].dropna().astype(str).str.strip().str.lower()
        hits = vals[vals.isin(placeholder_tokens)]
        if len(hits) > 0:
            found_placeholder = True
            print(f" ⚠️ Column '{col}': {len(hits)} placeholder-style value(s) found")
    if not found_placeholder:
        print(" No obvious text placeholders found.")

    # 3. Duplicates
    print("\n--- [3] DUPLICATE CHECK ---")
    print(f"Full identical rows: {df.duplicated().sum()}")
    id_cols = [c for c in df.columns if c.lower().endswith("_id")]
    for c in id_cols:
        dup = df[c].duplicated().sum()
        if dup > 0:
            print(f" ⚠️ Duplicates in ID column '{c}': {dup}")

    # 4. Text/category inconsistency — per-value case-style classification
    # (NOT a before/after-normalize count comparison — that misses same-count cases;
    #  NOT a compare-to-lowercase check — that false-positives on legitimately
    #  all-uppercase columns like IDs. Instead: classify each value's own style,
    #  then flag a column only if MULTIPLE styles co-exist within it.)
    #
    # KNOWN LIMITATION: Python's .istitle()/.isupper() are strict — a legitimately
    # correct brand name with an internal capital (e.g. "SwiftHaul") or an
    # abbreviation (e.g. "CO.", "Ltd.") won't match .istitle(), so this can still
    # flag already-clean data as "Mixed Case". Treat flags here as CANDIDATES for
    # manual review, not a definitive verdict — verify with .unique() before
    # deciding anything is actually wrong.
    print("\n--- [4] TEXT & CATEGORY INCONSISTENCY ---")

    def classify_style(value: str) -> str:
        v = str(value).strip()
        if v.isupper():
            return "UPPERCASE"
        if v.istitle():
            return "Title Case"
        if v.islower():
            return "lowercase"
        return "Mixed Case"

    found_text_issue = False
    for col in df.select_dtypes(include=["object"]):
        non_null = df[col].dropna().astype(str)
        if non_null.empty:
            continue
        styles = non_null.apply(classify_style).unique().tolist()
        if len(styles) > 1:
            found_text_issue = True
            print(f" ⚠️ Column '{col}': multiple case styles mixed -> {styles}")
        # also flag stray leading/trailing whitespace regardless of case style
        has_whitespace = (non_null != non_null.str.strip()).sum()
        if has_whitespace > 0:
            found_text_issue = True
            print(f" ⚠️ Column '{col}': {has_whitespace} value(s) with leading/trailing whitespace")
    if not found_text_issue:
        print(" No text/category inconsistency found.")

    # 5. Date column integrity
    print("\n--- [5] DATE COLUMN INTEGRITY ---")
    date_like_cols = [c for c in df.columns if "date" in c.lower()]
    if not date_like_cols:
        print(" No date-like columns in this table.")
    for c in date_like_cols:
        parsed = pd.to_datetime(df[c], format="mixed", dayfirst=True, errors="coerce")
        n_fail = parsed.isna().sum() - df[c].isna().sum()
        print(f" Column '{c}': {n_fail} value(s) failed to parse (excluding pre-existing NaN)")

    # 6. Numeric anomalies
    print("\n--- [6] STATISTICAL & NUMERIC ANOMALIES ---")
    numeric_cols = df.select_dtypes(include=["number"]).columns
    if len(numeric_cols) == 0:
        print(" No numeric columns in this table.")
    else:
        print(df[numeric_cols].agg(["min", "mean", "max"]).T)

    print("\n" + "=" * 60)
    print(" AUDIT COMPLETE")
    print("=" * 60)


def check_foreign_key(df: pd.DataFrame, fk_column: str, ref_df: pd.DataFrame, ref_id_column: str):
    """
    Check for orphan foreign keys: values in df[fk_column] that don't exist in
    ref_df[ref_id_column]. Run this separately for each FK relationship a table has
    (e.g. customers.preferred_store_id -> stores.store_id).
    """
    valid_ids = set(ref_df[ref_id_column].dropna())
    fk_values = df[fk_column].dropna()
    orphans = fk_values[~fk_values.isin(valid_ids)]
    print(f"\n--- FOREIGN KEY CHECK: {fk_column} -> {ref_id_column} ---")
    print(f"Orphan values found: {len(orphans)}")
    if len(orphans) > 0:
        print("Sample orphan values:", orphans.unique()[:10])
    return orphans


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python investigate.py path/to/table.csv")
        sys.exit(1)
    path = sys.argv[1]
    df = pd.read_csv(path)
    investigate(df, table_name=path)

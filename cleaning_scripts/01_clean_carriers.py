"""
Cleaning script for carriers.csv

Issue found: carrier_name has inconsistent case styles (mixed ALL CAPS / Title Case /
custom brand casing) across its 5 rows. See docs/CLEANING_LOG.md for the full
investigation, including two failed detection/fix attempts before this one.

Input:  raw carriers.csv (from the acpl-synthetic-dataset repo)
Output: data/carriers.csv (cleaned)
"""
import pandas as pd

RAW_PATH = "../acpl-synthetic-dataset/data/carriers.csv"  # adjust to your local path
OUTPUT_PATH = "../data/carriers.csv"

# Known-correct display names, keyed by an uppercased/stripped lookup so the mapping
# is robust regardless of whatever inconsistent case the raw value is in.
CORRECT_CARRIER_NAMES = {
    "SWIFTHAUL LOGISTICS": "SwiftHaul Logistics",
    "PADMA EXPRESS CARGO": "Padma Express Cargo",
    "JAMUNA FREIGHT CO.": "Jamuna Freight CO.",
    "DELTA TRANSPORT LTD.": "Delta Transport Ltd.",
    "MEGHNA MOVERS": "Meghna Movers",
}


def clean_carrier_name(name):
    if pd.isna(name):
        return name
    key = str(name).strip().upper()
    return CORRECT_CARRIER_NAMES.get(key, name.strip())


def main():
    df = pd.read_csv(RAW_PATH)
    df["carrier_name"] = df["carrier_name"].apply(clean_carrier_name)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Cleaned {len(df)} rows -> {OUTPUT_PATH}")
    print(df)


if __name__ == "__main__":
    main()

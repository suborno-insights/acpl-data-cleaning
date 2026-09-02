"""
Cleaning script for shipments.csv

Issues found (see docs/CLEANING_LOG.md for the full investigation -- this table's
most important finding, a mixed-unit bug, was invisible to investigate.py entirely):
1. dispatch_date/expected_arrival_date/actual_arrival_date: mixed date formats.
2. shipment_status: false positive (data already clean; hyphenated values just
   break Python's strict .istitle()).
3. shipment_id: 89 real duplicates, only detectable after fixing ALL THREE date
   columns (same root cause as po_id/transaction_id).
4. actual_arrival_date missing (25): verified 100% consistent with
   shipment_status == 'In-Transit' -- left untouched.
5. distance_km: a mixed-unit bug (km vs. miles) invisible to any generic numeric
   check -- detected via route-level consistency (same warehouse+store pair should
   always have the same distance), confirmed by a precise ~1.609 (km-per-mile)
   ratio repeating across 42 independent routes. Fixed by replacing the smaller
   (miles-in-disguise) value with the larger (correct km) value per route.
6. store_id == 'ST99' (33 rows): an orphan foreign key. Recovery via nearest-
   distance-match attempted and rejected -- 4 equally-plausible candidate stores,
   no verified single answer -- flagged instead of corrected or deleted.
7. shipment_cost missing (462): no pattern found against shipment_status or the
   store_id flag; route-level cost consistency was too inconsistent across routes
   to support a uniform recovery rule -- left as NaN rather than introduce an
   arbitrary per-route threshold.

Input:  raw shipments.csv (from the acpl-synthetic-dataset repo)
Output: data/shipments.csv (cleaned)
"""
import pandas as pd

RAW_PATH = "../acpl-synthetic-dataset/data/shipments.csv"  # adjust to your local path
OUTPUT_PATH = "../data/shipments.csv"


def main():
    df = pd.read_csv(RAW_PATH)
    before_shape = df.shape

    # Fix 1: mixed date formats -> real datetime type. Must happen before the
    # shipment_id duplicate check below.
    df["dispatch_date"] = pd.to_datetime(df["dispatch_date"], format="mixed", dayfirst=True, errors="coerce")
    df["expected_arrival_date"] = pd.to_datetime(df["expected_arrival_date"], format="mixed", dayfirst=True, errors="coerce")
    df["actual_arrival_date"] = pd.to_datetime(df["actual_arrival_date"], format="mixed", dayfirst=True, errors="coerce")

    # shipment_status: no fix needed -- verified already clean, the "Mixed Case"
    # flag was a false positive from hyphenated values.

    # Fix 2: shipment_id duplicates, now correctly detectable post date-fix.
    df = df.drop_duplicates(subset=["shipment_id"], keep="first")

    # actual_arrival_date missing (25) intentionally left as-is -- verified
    # consistent with shipment_status == 'In-Transit'.

    # Fix 3: distance_km mixed units (km vs miles). Detected via route-level
    # consistency; the smaller of two values per route is the miles-in-disguise one.
    route_stats = df.groupby(["warehouse_id", "store_id"])["distance_km"].agg(["min", "max", "nunique"]).reset_index()
    route_stats["ratio"] = route_stats["max"] / route_stats["min"]
    suspicious_routes = route_stats[(route_stats["nunique"] == 2) & (route_stats["ratio"].between(1.55, 1.65))]
    for _, route in suspicious_routes.iterrows():
        wh, st, correct_km = route["warehouse_id"], route["store_id"], route["max"]
        mask = (df["warehouse_id"] == wh) & (df["store_id"] == st) & (df["distance_km"] == route["min"])
        df.loc[mask, "distance_km"] = correct_km

    # Fix 4: orphan store_id ('ST99') -- flagged, not corrected (no single
    # verified candidate store; multiple routes were similarly plausible).
    df["store_id_invalid_flag"] = df["store_id"] == "ST99"

    # shipment_cost missing (462) intentionally left as-is -- no clean pattern
    # found, and route-level cost consistency was too variable to support a
    # uniform recovery rule.

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Before: {before_shape} -> After: {df.shape}")
    print(f"Saved -> {OUTPUT_PATH}")
    print(f"shipment_id duplicates remaining: {df.duplicated(subset=['shipment_id']).sum()}")
    print(f"Routes still showing >1 distinct distance_km: {(df.groupby(['warehouse_id','store_id'])['distance_km'].nunique() > 1).sum()}")
    print(f"store_id_invalid_flag count: {df['store_id_invalid_flag'].sum()}")
    print(f"shipment_cost missing (left as NaN): {df['shipment_cost'].isna().sum()}")


if __name__ == "__main__":
    main()

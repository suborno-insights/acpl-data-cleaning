# 🧹 ACPL Data Cleaning

**Status: Complete — all 11 tables investigated and cleaned.**

Hands-on data cleaning practice on a large, intentionally-messy synthetic retail dataset —
finding and fixing real-world-style data quality issues myself, one table at a time.

## 🎯 Why this exists

The raw dataset lives in a separate repo — **[acpl-synthetic-dataset](https://github.com/suborno-insights/acpl-synthetic-dataset.git)**
— which I designed and generated with 11 interlinked tables, deliberately messy (missing
values, duplicates, inconsistent formats, outliers, and more). That repo documents *which
types* of issues exist per table, but never the exact row-level answers — on purpose, so
that cleaning it is a genuine exercise, not a lookup.

This repo is where I do that exercise: investigate each table myself, find the issues,
decide how to fix them, and document my reasoning — including the mistakes I make and
correct along the way, because that's the real part of the job.

## 🧭 Approach

For each table:
1. **Investigate** — structure, missing values, duplicates, text/category inconsistency,
   date integrity, numeric anomalies, referential integrity
2. **Decide** — what's actually broken vs. what only looks broken (false positives matter)
3. **Fix** — always from a fresh copy of the raw data, one clean deterministic script per
   table, no patch-on-patch
4. **Document** — what I found, how I found it, and why I fixed it the way I did

## 📁 Structure

```
acpl-data-cleaning/
├── README.md
├── cleaning/
│   ├── investigate.py               # reusable investigation script (run on any table)
│   ├── clean_carriers.py
│   ├── clean_customers.py
│   ├── clean_inventory_snapshots.py
│   ├── clean_products.py
│   ├── clean_promotions.py
│   ├── clean_purchase_orders.py
│   ├── clean_sales_transactions.py
│   ├── clean_shipments.py
│   ├── clean_stores.py
│   ├── clean_suppliers.py
│   └── clean_warehouses.py
├── data/                # cleaned CSV output, one file per table
└── docs/
    └── CLEANING_LOG.md   # per-table findings: issue -> detection method -> fix,
                           # plus a series summary at the end
```

## ✅ Progress

All 11 tables done.

| Table | Status |
|---|---|
| carriers | ✅ Done |
| customers | ✅ Done |
| inventory_snapshots | ✅ Done |
| products | ✅ Done |
| promotions | ✅ Done |
| purchase_orders | ✅ Done |
| sales_transactions | ✅ Done |
| shipments | ✅ Done |
| stores | ✅ Done |
| suppliers | ✅ Done |
| warehouses | ✅ Done |

## 🔑 Highlights

A few of the more interesting findings, out of the full write-up in
[`docs/CLEANING_LOG.md`](CLEANING_LOG.md):

- **A completely invisible-to-automation bug**: `shipments.distance_km` had some values
  recorded in miles instead of km — no single-column check can catch this, since a mile
  value looks just as "normal" as a km value. Found by checking that every (warehouse,
  store) route should always report the same distance, and confirming a precise 1.609
  (km-per-mile) ratio repeating across 42 independent routes.
- **Duplicates hidden behind more than one column**: `sales_transactions.transaction_id`'s
  real duplicates only became detectable after fixing *both* mixed date formats *and*
  inconsistent `payment_method` casing — fixing dates alone wasn't enough.
- **A business rule proven from the data, not assumed**: confirmed with zero
  counterexamples that no-promotion transactions always have a 0% discount, before using
  that rule to justify filling ~19,000 missing values with a data-verified `0`.
- **Knowing when *not* to guess**: several issues (an unrecoverable 10x-typo outlier, an
  orphan `store_id` with 4 equally-plausible candidate matches, a cross-column quantity
  mismatch with no fixable answer) were flagged or left as `NaN` rather than resolved with
  a plausible-but-unverifiable guess.

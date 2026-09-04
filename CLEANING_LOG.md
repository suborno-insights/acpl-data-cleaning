# 🧹 Cleaning Log

Per-table record of issues found, how they were detected, and how they were fixed.
Written as I go — including dead ends, because those are part of the real process.

---

## 🚚 `carriers.csv`

### Investigation summary

| Check | Result |
|---|---|
| Missing values | None |
| Duplicates (full row / ID key) | None |
| Text/category inconsistency | **Found** — `carrier_name` has mixed case styles |
| Date integrity | N/A (no date column) |
| Numeric anomalies (`base_reliability`) | None (all values within 0–1) |

### The issue

`carrier_name` mixed three different case styles across its 5 rows:

```
'SwiftHaul Logistics'    (custom brand casing)
'PADMA EXPRESS CARGO'    (ALL CAPS)
'JAMUNA FREIGHT CO.'     (ALL CAPS)
'Delta Transport Ltd.'   (Title Case)
'Meghna Movers'          (Title Case)
```

### Detection — two failed attempts before the right one

1. **First attempt**: compared `nunique()` before vs. after normalizing (lowercasing +
   stripping). This only catches inconsistency when two *different-looking* values collapse
   into the *same* value after normalizing (e.g. duplicates in different cases). It missed
   this issue entirely, because all 5 carrier names are genuinely distinct — normalizing
   doesn't reduce the count, so the check silently passed.

2. **Second attempt**: compared each value to its own lowercased version
   (`value != value.strip().lower()`). This produced false positives on `carrier_id`
   (`CR01`, `CR02`, ...) — those are *supposed* to be uppercase; comparing against lowercase
   flags every single correctly-formatted ID as "inconsistent."

3. **Working approach**: instead of comparing values to a normalized version, classify each
   value's actual case *style* (upper / title / mixed, via `.isupper()`/`.istitle()`) and
   check whether **multiple different styles co-exist within the same column**. This
   correctly passed `carrier_id` (single consistent style: all-uppercase) and correctly
   flagged `carrier_name` (three different styles mixed together).

### Fixing — one failed attempt before the right one

1. **First attempt**: a "smart title case" function — lowercase everything, then
   `.capitalize()` each word, with a hardcoded set of words (`CO`, `LTD`, etc.) forced to
   uppercase. This handled `CO.`/`LTD.` correctly, but broke the legitimate brand casing
   `SwiftHaul` → `Swifthaul` (the internal capital H is intentional branding, not
   inconsistency — blanket `.capitalize()` can't tell the difference).

2. **Working approach**: a small mapping dictionary (`{uppercased_name: correct_display_name}`)
   with case-insensitive lookup. Since only 5 carriers exist and they're all known values,
   this is both simpler and safer than a general-purpose text-normalization rule — no risk
   of over-correcting a legitimate brand name. **Re-ran on a fresh copy of the raw CSV**
   (not on the already-corrupted output from the failed attempt) to avoid stacking a fix on
   top of a bug.

### Result

```
carrier_id  carrier_name           base_reliability
CR01        SwiftHaul Logistics    0.90
CR02        Padma Express Cargo    0.82
CR03        Jamuna Freight CO.     0.88
CR04        Delta Transport Ltd.   0.70
CR05        Meghna Movers          0.93
```

### Lessons

- A detection rule that just checks "did the count change after normalizing" misses
  same-count-but-inconsistent-style problems — need to check per-value style, not aggregate
  counts.
- A detection rule that compares every value against one fixed target style (e.g. lowercase)
  produces false positives on columns that have their own different, legitimate standard
  style (e.g. all-caps IDs).
- Blind text-normalization functions (`.capitalize()`, `.upper()`) can silently destroy
  legitimate mixed-case data (brand names, proper nouns). For small, known-value columns, an
  explicit mapping table is safer than a general rule.
- When a fix goes wrong, re-run from the original raw data — don't patch a patch.
- **Follow-up finding**: after generalizing this detection logic into a reusable
  `investigate.py` for future tables, running it against the *already-cleaned*
  `carriers.csv` still flagged `carrier_name` as "Mixed Case" — Python's `.istitle()` is
  strict and doesn't recognize legitimate brand casing (`SwiftHaul`'s internal capital) or
  abbreviations (`CO.`, `Ltd.`) as valid title case. This isn't a fixable bug so much as a
  fundamental limit of rule-based case detection — brand-name style can't be fully
  automated. `investigate.py` now documents this explicitly: its case-style flags are
  candidates for manual review, not a final verdict.

---

## 👥 `customers.csv`

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `region`: 446 missing (7.38%) |
| Duplicates (full row) | 40 |
| Text/category inconsistency | **Found** — `region` has real case + whitespace inconsistency |
| Date integrity | `join_date` parses fine, but is a mixed-format issue mislabeled by the style checker (see below) |
| Numeric anomalies | N/A (no numeric columns) |

### Two false positives caught before trusting the flags

`investigate.py` flagged 4 columns as having issues. Two turned out to be real problems and
two were false positives — each verified individually before acting on it, per the lesson
already learned on `carriers.csv`.

1. **`preferred_store_id` flagged as "6020 duplicates"** — false positive. This column is a
   foreign key (many customers share the same preferred store), not a primary key, so
   repeated values are expected and correct. Verified with:
   ```python
   df['preferred_store_id'].nunique()  # -> 20 (matches the 20 stores)
   ```
   and confirmed there were zero orphan references against `stores.store_id` via the
   `check_foreign_key()` helper. No action needed.

2. **`acquisition_channel` flagged as "Mixed Case Styles"** — false positive, same root
   cause as the `carriers.csv` brand-name issue: the value `'Walk-in'` contains a hyphen,
   which breaks Python's `.istitle()` even though the value is already correctly formatted.
   Verified with `.unique()` — all 4 values (`Walk-in`, `Referral`, `Online`,
   `Social Media`) were already consistent. No action needed.

3. **`join_date` flagged as "Mixed Case Styles"** — this one WAS a real issue, just
   mislabeled. The case-style checker doesn't apply meaningfully to a date column; what it
   was actually detecting was **three different date string formats mixed together**
   (`DD/MM/YYYY`, `YYYY-MM-DD`, and `Month D, YYYY`), confirmed by inspecting raw values with
   `.head(10).tolist()`.

### The real issues, and how they were fixed

**`join_date` — mixed date formats.** Fixed with:
```python
df['join_date'] = pd.to_datetime(df['join_date'], format='mixed', dayfirst=True, errors='coerce')
```
`dayfirst=True` matters here — without it, ambiguous `DD/MM/YYYY` values (day ≤ 12) get
misread as `MM/DD/YYYY` (same ambiguity documented in the source dataset's own
`ENGINEERING_PROCESS.md`). Confirmed 0 parse failures after conversion.

**`region` — case + whitespace inconsistency.** 24 raw variants (e.g. `'Dhaka'`, `'DHAKA'`,
`'dhaka'`, `' Dhaka '`) collapsed into 6 clean region names with:
```python
df['region'] = df['region'].str.strip().str.title()
```
No brand-name-style exceptions here (unlike `carriers.csv`), so the generic method was
safe to use as-is — verified `NaN` passed through untouched (missing count stayed at 446
before and after).

**`region` — 446 missing values.** Left untouched deliberately; a decision on how to handle
them (drop, impute, flag as "Unknown") is left for whichever downstream project actually
needs `region` as a feature, rather than guessed at during cleaning.

**Duplicate rows (40).** Removed with `df.drop_duplicates()`. Row count confirmed dropping
from 6040 to 6000.

### A costly notebook mistake (and the fix)

After applying all of the above, `df.to_csv('customers_cleaned.csv', index=False)` was run
— but the saved file still showed the raw, unfixed `join_date` values. Root cause:
`investigate.py`'s audit function was re-run afterward for a sanity check, and it contains
its own `df = pd.read_csv(csv_path)` — re-running that cell silently reloaded the raw file
into `df`, overwriting every fix made so far. The save then wrote out the *reloaded raw*
data, not the cleaned one.

**Fix**: re-ran every step — load, `join_date` fix, `region` fix, `drop_duplicates()`,
verify, save — as one uninterrupted, ordered sequence, without re-running the
investigation/audit cell in between.

### Lessons

- Every flag from `investigate.py` needs individual verification — in this one table, half
  the flags (2 of 4) were false positives, for two different underlying reasons (FK
  cardinality mistaken for a duplicate-key problem; brand/format quirks breaking
  `.istitle()`).
- A generic issue-detection script can mislabel a real issue's *category* (this flagged a
  date-format problem as a "case style" problem) even while still being useful for
  *noticing* that something's off in the column — the flag was a correct signal, wrongly
  explained.
- In a notebook environment, cell execution order — not the order cells are written in —
  determines what `df` actually contains. Re-running any cell that reloads from disk
  (`pd.read_csv`) silently discards all in-memory fixes made after it. Once fixes are
  verified, run load -> fix -> fix -> verify -> save as one uninterrupted sequence.

---

## 📊 `inventory_snapshots.csv`

The most involved table cleaned so far — several issues here needed reasoning beyond
"detect and fix," including one genuine logical-inconsistency finding.

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `stock_qty`: 3,279 missing (3.9%) |
| Duplicates (single-column ID check) | False alarm — see below |
| Text/category inconsistency | `snapshot_date` flagged, but mislabeled (see below) |
| Date integrity | 0 parse failures once fixed |
| Numeric anomalies | **115 negative `stock_qty` values** |

### False positive #1 — single-column "duplicate" check on a snapshot table

`investigate.py`'s generic ID-duplicate check flagged `product_id` (84,032 "duplicates")
and `warehouse_id` (84,177 "duplicates") — alarming numbers on their own. But this table's
grain is **one row per (product, warehouse, date)**, not one row per product or per
warehouse — of course the same product/warehouse ID repeats across every snapshot date.
Verified two ways:

```python
df['product_id'].nunique()    # 148 (matches the 148 real products)
df['warehouse_id'].nunique()  # 3   (matches the 3 real warehouses)
df.duplicated(subset=['product_id','warehouse_id','snapshot_date']).sum()  # 0
```

The correct duplicate check for a table like this is on the **composite key**
(product + warehouse + date together), not any single ID column alone — a generic
single-column check isn't the right tool for every table's grain.

### False positive #2 — `.head()` lied, `.sample()` told the truth

`snapshot_date` was flagged as "Mixed Case Styles" (the same date-vs-case-checker
mislabeling seen on `join_date` in `customers.csv`). But when first inspected with
`.head(10)`, all 10 values happened to be in the same `DD/MM/YYYY` format — looking clean.
Only after checking a **random sample** (`.sample(15, random_state=1)`) did the real mix of
three formats (ISO, `DD/MM/YYYY`, `Month D, YYYY`) show up. **Lesson**: `.head()` only shows
the start of the data and can give a false sense of "this looks fine" on a large table —
`.sample()` (or a full-column check like the date-parse-failure count) is the reliable way
to verify a column-wide claim.

### The real issue — `stock_qty` negative values (115)

Before deciding how to fix a negative-value issue like this, the question isn't just "how do
I make it positive" — it's "do I even understand *why* it's negative first." Checked whether
the magnitude (ignoring sign) of the negative values looked like plausible stock quantities,
by comparing distributions:

```python
df.loc[df['stock_qty'] < 0, 'stock_qty'].abs().describe()   # mean ~3888, max ~16944
df.loc[df['stock_qty'] >= 0, 'stock_qty'].describe()         # mean ~3097, max ~21433
```

The negative values' magnitudes fell within the same range as normal positive stock
quantities — consistent with a **sign-flip type error**, not fabricated/garbage numbers.
That evidence justified a simple fix:

```python
df['stock_qty'] = df['stock_qty'].abs()
```

Row count and missing-value count were unaffected — only the sign of 115 values changed.

### The real issue — `stock_qty` missing values (3,279), and why "leave it" was wrong here

This is the most important finding on this table. It would have been easy to apply the same
"leave missing values untouched" decision made for `customers.region` — but that decision
doesn't automatically transfer between columns. Checking whether the missing rows showed any
**internal contradiction** with other columns revealed one:

```python
df[df['stock_qty'].isna()]['stockout_flag'].value_counts()
# False    2765
# True      514
```

`stockout_flag` is meant to be *derived from* `stock_qty` (stock <= 0 -> stockout). Having a
confident `True`/`False` value for a flag while the very number it should be derived from is
missing is a logical inconsistency, not a neutral "this data point wasn't collected." That
distinguishes it from `region` (a standalone attribute with no such downstream contradiction)
and meant "leave it blank" was not an acceptable choice here.

**Fix — linear interpolation**, chosen because `stock_qty` is a time series per
product+warehouse (unlike a static category like `region`, which cannot be reasonably
"interpolated" from neighboring rows):

```python
df = df.sort_values(['product_id', 'warehouse_id', 'snapshot_date'])
df['stock_qty_was_missing'] = df['stock_qty'].isna()  # keep a record of which values are estimates
df['stock_qty'] = df.groupby(['product_id', 'warehouse_id'])['stock_qty'].transform(
    lambda x: x.interpolate(method='linear', limit_direction='both')
)
```

- Grouped by `product_id` + `warehouse_id` — one product's stock trend shouldn't influence
  another's.
- `limit_direction='both'` handles missing values at the very start/end of a group's
  timeline, where plain linear interpolation (which needs a value on both sides) can't reach
  — 13 such edge-case rows needed this before the missing count hit 0.
- Kept `stock_qty_was_missing` as a flag column rather than deleting the distinction between
  observed and estimated values — future analysis should be able to tell them apart.
- Verified the interpolated values didn't introduce new negative values (a real risk with
  linear interpolation around a stockout dip) — confirmed 0.

### Fixing `snapshot_date`

Same fix as `customers.join_date`, same reasoning:
```python
df['snapshot_date'] = pd.to_datetime(df['snapshot_date'], format='mixed', dayfirst=True, errors='coerce')
```

### Lessons

- A generic "duplicate ID" check assumes one row = one ID, which breaks on any table whose
  real grain is a composite key (like a snapshot table). Check duplicates on the actual
  grain, not a convenient single column.
- `.head()` shows the *start* of a column, not a representative view of it — a column can
  look uniform in the first 10 rows and still be a mess overall. Use `.sample()` or a
  full-column check to verify a claim about the whole column.
- Before fixing a numeric anomaly (like negative values), check *why* it might be wrong —
  comparing magnitude distributions can distinguish a plausible sign-flip bug from
  fabricated/garbage data, which would need a different fix entirely (or no fix — deletion).
- The "leave missing values untouched" decision made for one column doesn't automatically
  apply to another — check whether missing values in this column contradict other columns
  in the same row. A flag column that's supposedly derived from the missing column is a sign
  the missingness isn't neutral.
- Time-series-shaped data (a value that changes gradually over time, grouped by an entity)
  can support interpolation as a fill strategy; a static categorical attribute (like
  `region`) cannot — the fill strategy has to match the nature of the column, not just be
  copy-pasted from the last table.
- When estimating missing values, keep a record of which values were estimated vs. observed
  (`stock_qty_was_missing`) rather than making them indistinguishable from real data.

---

## 📦 `products.csv`

The table with the widest variety of issue types so far — a hidden dtype problem, a
zero-price business-logic violation, a real case/whitespace mess, and two numeric outliers
that needed genuinely different fixes despite looking similar on the surface.

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `unit_cost`: 5 missing (2.76%) |
| Duplicates | 1 full identical row |
| Text/category inconsistency | `category` — real case + whitespace issue |
| Date integrity | `launch_date` — 0 parse failures once fixed |
| Numeric anomalies | `unit_cost`: 1 negative value + 1 extreme outlier; `unit_price`: hidden entirely (see below) |

### The hidden issue `investigate.py` never flagged — `unit_price` wasn't numeric at all

`unit_cost` was `float64`, but `unit_price` was `object` (text) — a dtype mismatch between
two columns that should both obviously be numeric. The cause: some `unit_price` values were
stored as plain numeric strings (`'309.39'`), and others had a `৳` currency symbol baked
into the string (`'৳157.52'`). A single non-numeric-looking value anywhere in a column is
enough to force the *entire* column to `object` dtype in pandas — including all the
"normal-looking" values, which become strings too, not real numbers.

**This is exactly the kind of issue a generic script can silently miss**: `investigate.py`'s
numeric-anomaly check only looks at columns pandas already recognizes as numeric
(`select_dtypes(include=['number'])`). Since `unit_price`'s dtype was `object`, it was
silently excluded from that check entirely — no warning, no flag, nothing. It only surfaced
by noticing the dtype mismatch against `unit_cost` in Section 1 and asking *why* two
price-like columns had different types.

**Fix** — two separate steps, because removing the symbol and converting the type are
different operations:
```python
df['unit_price'] = df['unit_price'].str.replace('৳', '', regex=False)
df['unit_price'] = pd.to_numeric(df['unit_price'])
```

### `unit_price` = 0 — a business-logic violation, not a formatting issue

Once `unit_price` was numeric, its `describe()` showed `min: 0.0` — no product can
legitimately cost nothing. Located the row (`P053`) and checked its context: `unit_cost`
was a normal 111.17, and `is_active` was `True` (not a discontinued product with no
current price) — so `0` wasn't explainable as "discontinued, price cleared." This was
confirmed to be one of the dataset's intentionally-injected outliers (documented in the
source repo's own engineering notes — a deliberately corrupted zero price).

**Decision**: convert to `NaN` rather than guess a replacement value. There is no way to
mathematically recover "what the real price was" from a `0` — any replacement would be
fabricated data dressed up as real data.
```python
df.loc[df['unit_price'] == 0, 'unit_price'] = pd.NA
```

### `category` — real case + whitespace inconsistency (26 -> 8 clean values)

Same shape of problem as `customers.region`: 26 raw variants (`'HOME & KITCHEN'`,
`'Home & Kitchen'`, `' Home & Kitchen '`, etc.) collapsing into 8 real categories. No
brand-name-style legitimate exceptions this time (unlike `carrier_name`), so the generic
fix was safe as-is — including verifying the `&` character in `'Home & Kitchen'` survived
`.str.title()` correctly:
```python
df['category'] = df['category'].str.strip().str.title()
```

### `unit_cost` — two numeric anomalies that looked similar but needed different fixes

Both were flagged by `investigate.py`'s negative-value / min-max check, but they required
genuinely different decisions — a good example of why "the same kind of flag" doesn't mean
"the same kind of fix."

**1. One negative value (`-107.05`, product `P046`)** — verified via a derived
margin-percentage check before fixing, rather than assuming `.abs()` was safe just because
it worked on `inventory_snapshots.stock_qty`:
```python
df['margin_pct_check'] = (df['unit_price'] - df['unit_cost'].abs()) / df['unit_price'] * 100
```
P046's implied margin, treating the cost as positive, came out to 28.76% — squarely inside
the normal range seen across the rest of the (already-clean) products (25th percentile
18.3%, 75th percentile 27.0%). That's strong evidence this was a **sign-flip error**, not a
fabricated number, so `.abs()` was a justified, verified fix — not just a guess.
```python
df['unit_cost'] = df['unit_cost'].abs()
```

**2. One extreme outlier (`4206.70`, product `P180`)**, unit_price only 568.92 — implying
the company loses ~3,638 per unit sold, which makes no business sense. This *looked* like a
plausible "extra zero" data-entry typo (i.e., real value probably `420.67`), but unlike the
negative-value case, **dividing by 10 cannot be verified** — there's no mathematical
certainty behind it, only a plausible story. Applying the same principle used for
`unit_price = 0`: a fix that can't be verified is a guess, not a correction.
```python
df.loc[df['product_id'] == 'P180', 'unit_cost'] = pd.NA
```

### Duplicate row

Unlike the false-positive duplicate flags on earlier tables, this one was real — a full
identical row for `product_id` `P006` (every column matched, not just the ID). Removed
using an explicit `subset=['product_id']` rather than a bare `.drop_duplicates()`, since
`product_id` is the actual primary key that should never repeat, regardless of whether every
other column happens to match too:
```python
df = df.drop_duplicates(subset=['product_id'], keep='first')
```

### Lessons

- A column's dtype can hide an entire category of problems from a generic numeric-anomaly
  check. If two columns *should* both be numeric (e.g. cost and price) but have different
  dtypes, that mismatch itself is worth investigating before trusting any "no numeric
  issues found" result.
- Fixing a symbol-contaminated numeric column is two separate steps: strip the
  non-numeric characters first, then convert the type — doing both at once tends to hide
  which step actually failed if something goes wrong.
- Not every zero/negative/outlier value has the same kind of fix, even within the same
  column. `-107.05` (verified via margin-consistency check) got `.abs()`'d; `4206.70`
  (an unverifiable "maybe extra zero" guess) got set to `NaN` instead, and `0` (a
  business-logic-impossible price) also got set to `NaN` — three different values in two
  price columns, three different decisions, based on how *verifiable* each fix was, not
  just on the value's shape.
- A derived metric (margin % from cost and price together) can validate a single-column
  outlier fix more convincingly than looking at that column in isolation.
- When two numeric anomalies could both plausibly be explained by a simple transformation
  (sign flip, decimal/zero shift), only apply the transformation if it's mathematically
  certain (like a sign flip) — not just plausible (like "maybe an extra zero").

---

## 🏷️ `promotions.csv`

A shorter, more confident pass — most of the issue types here matched patterns already seen
on earlier tables, letting each one be verified and resolved quickly.

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `discount_pct`: 12 missing (6.32%) |
| Duplicates | 0 full-row; `product_id` "78 duplicates" flagged (false positive, see below) |
| Text/category inconsistency | `start_date`/`end_date` mislabeled (date-format issue); `channel` — real case + whitespace issue |
| Date integrity | 0 parse failures once fixed |
| Numeric anomalies | None (`discount_pct` range 10.0–45.0, no negatives/zeros) |

### False positive — `product_id` "78 duplicates"

Same reasoning as `inventory_snapshots.product_id`/`warehouse_id` and
`customers.preferred_store_id`: this table's grain is **one row per promotion event**, and a
single product can legitimately run multiple promotions over time. Repeated `product_id`
values are expected, not a data-quality issue. No verification code needed beyond
recognizing the table's grain — correctly identified without running anything.

### `start_date` / `end_date` — mislabeled date-format issue (now a recognized pattern)

Flagged as "Mixed Case Styles" by `investigate.py`, same as `customers.join_date` and
`inventory_snapshots.snapshot_date` before it. Verified with `.sample(10, random_state=1)`
(not `.head()`, learning from the `inventory_snapshots` false-clean-looking-`.head()`
mistake) and confirmed the same three mixed formats (ISO, `DD/MM/YYYY`, `Month D, YYYY`).
Fixed identically:
```python
df['start_date'] = pd.to_datetime(df['start_date'], format='mixed', dayfirst=True, errors='coerce')
df['end_date'] = pd.to_datetime(df['end_date'], format='mixed', dayfirst=True, errors='coerce')
```

### `channel` — real case + whitespace inconsistency, with a useful detection-vs-fixing distinction

`.unique()` showed 10 raw variants of 3 real values (`Both`/`BOTH`/`both`,
`In-store`/`IN-STORE`/`' In-store '`/`in-store`, `Online`/`ONLINE`/`online`). Initially
suspected `In-store`'s hyphen might cause the same kind of problem as `Walk-in` did on
`customers.acquisition_channel` — but a quick isolated test showed the fix function handles
it fine:
```python
pd.Series(['In-store', 'IN-STORE', ' In-store ', 'in-store']).str.strip().str.title()
# -> all four become 'In-Store'
```
**Key distinction**: `Walk-in`'s hyphen broke *detection* (`.istitle()` doesn't recognize a
hyphenated word as valid title case, causing a false-positive flag), but the same hyphen does
**not** break *fixing* (`.str.title()` correctly treats the hyphen as a word boundary, same
as a space). A bug in one operation doesn't imply the same bug exists in a related-looking
operation — each needs its own verification.
```python
df['channel'] = df['channel'].str.strip().str.title()
```
Result: 3 clean values (`Both`, `In-Store`, `Online`).

### `discount_pct` — 12 missing values, left untouched (a two-part justification)

Checked two things before deciding, applying the same standard used on
`inventory_snapshots.stock_qty` and `customers.region`:

1. **Internal contradiction check** — inspected the 12 affected rows' other columns
   (`campaign_name`, `start_date`, `end_date`, `channel`) and found them all complete and
   consistent. No sign of a derived-field contradiction like the `stock_qty`/`stockout_flag`
   case.
2. **Business-plausibility check** — is a promotion with no percentage discount actually
   possible, or is `0`/missing here more like `unit_price = 0` (an impossible value)? Unlike
   a price of 0, a promotion legitimately not having a percentage discount is plausible (a
   flat-amount deal, a BOGO-style offer, etc.) — this isn't a value that's *impossible*, just
   not applicable to every promotion.

**Decision**: leave as `NaN`, the same choice as `customers.region`, but for a more
deliberately reasoned combination of checks rather than by default.

### Lessons

- Recognizing a table's grain (one row per what, exactly?) before running any duplicate
  check saves time — the `product_id` "duplicate" flag here was dismissed correctly without
  needing to run verification code, because the pattern (one entity, many events) was
  already familiar from two earlier tables.
- A detection bug (e.g. `.istitle()` false-flagging a hyphenated value) does not
  automatically mean the corresponding fix function has the same bug — verify each
  operation independently, ideally with a small isolated test before touching the real data.
- Deciding to leave missing values untouched should rest on two separate checks, not one:
  whether the missingness contradicts other columns in the same row (it didn't here), *and*
  whether the underlying real-world scenario the missing value represents is actually
  possible (it is — not every promotion needs a percentage discount). A value can pass one
  check and still fail the other.

---

## 🧾 `purchase_orders.csv`

The most involved table cleaned so far — a duplicate check that only worked *after* fixing
a different column first, and a cross-column numeric inconsistency with no fixable answer,
only an honest way to flag it.

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `actual_delivery_date`: 365 (1.29%); `qty_rejected`: 1,905 (6.72%); `rejection_reason`: 235 (0.83%) |
| Duplicates | 3 full-row (by string match); **140 real `po_id` duplicates hidden behind mixed date formats** (see below) |
| Text/category inconsistency | 3 date columns mislabeled (date-format issue, familiar pattern); `rejection_reason` — real case + whitespace issue |
| Date integrity | 0 parse failures once fixed |
| Numeric anomalies | `order_qty`: 77 negative values; **a cross-column inconsistency between `order_qty`, `qty_received`, and `qty_rejected` that `investigate.py` cannot detect at all** (single-column tool, this needed a multi-column check) |

### `supplier_id`/`product_id`/`warehouse_id` "duplicates" — recognized as false positives without running any code

By this table, the foreign-key-vs-primary-key distinction (first learned on
`customers.preferred_store_id`) was familiar enough to dismiss these flags correctly on
sight — a purchase order table's grain is one row per order event, and the same
supplier/product/warehouse legitimately appears across many orders.

### `po_id` — a real duplicate, but only visible after fixing dates first

`po_id` **is** meant to be a real primary key (verified: `df['po_id'].nunique()` = 28,188
vs. `len(df)` = 28,328 — a genuine gap, unlike the false-positive checks above). But a naive
`.duplicated(subset=['po_id'])` alone wasn't enough to understand *why* — inspecting the
duplicate pairs directly (`df[df.duplicated(subset=['po_id'], keep=False)]`) showed every
other column matching exactly between pairs, **except the date columns**, which held the
same date written in different formats (e.g. `'22/11/2024'` vs `'November 22, 2024'`) —
identical information, different text representation, so pandas' exact-string duplicate
check didn't catch them as matching rows.

**Fix order mattered here**: converting the date columns to real `datetime64` *first*
(same `pd.to_datetime(format='mixed', dayfirst=True)` fix as every other date column in
this dataset) made the previously-different-looking date strings become genuinely equal
`Timestamp` objects — only then did `.duplicated(subset=['po_id'])` correctly find all 140
pairs. Running the duplicate check before the date fix would have found nothing, since the
rows weren't string-identical yet.
```python
df['order_date'] = pd.to_datetime(df['order_date'], format='mixed', dayfirst=True, errors='coerce')
df['expected_delivery_date'] = pd.to_datetime(df['expected_delivery_date'], format='mixed', dayfirst=True, errors='coerce')
df['actual_delivery_date'] = pd.to_datetime(df['actual_delivery_date'], format='mixed', dayfirst=True, errors='coerce')
df = df.drop_duplicates(subset=['po_id'], keep='first')
```
Row count dropped from 28,328 to 28,188 — exactly the 140-row gap identified earlier.

### `actual_delivery_date` — 365 missing values, verified against `po_status`

Checked whether the missingness contradicted another column before deciding, the same
standard applied on `inventory_snapshots.stock_qty`:
```python
df[df['actual_delivery_date'].isna()]['po_status'].value_counts()
# Pending    365
```
All 365 rows, with zero exceptions, had `po_status == 'Pending'` — a delivery that hasn't
happened yet has no delivery date, which is the *correct* state, not missing data. Left
untouched.

### `order_qty` — 77 negative values, verified via magnitude comparison

Same method as `unit_cost`'s negative value on `products.csv`: compared the absolute value
of the negative entries against the normal positive distribution.
```python
df.loc[df['order_qty'] < 0, 'order_qty'].abs().describe()   # mean ~422, max ~745
df.loc[df['order_qty'] >= 0, 'order_qty'].describe()         # mean ~400, max ~869
```
Distributions matched closely — consistent with a sign-flip error, not fabricated numbers.
```python
df['order_qty'] = df['order_qty'].abs()
```

### The big one — `order_qty` vs. `qty_received` + `qty_rejected` don't add up, and there's no way to fix it

This table has three related quantity columns that should satisfy a basic accounting
identity: everything ordered should end up either received (accepted) or rejected. Checking
this required comparing **three columns at once** — something `investigate.py`'s
single-column checks are structurally incapable of catching; this had to be reasoned about
and written from scratch.

**First attempt had a bug**: a naive `qty_received + qty_rejected != order_qty` check
flagged 2,230 rows, but most of that count turned out to be an artifact — wherever
`qty_rejected` was `NaN`, the addition itself became `NaN`, and `NaN != anything` is always
`True` in pandas, so every missing-`qty_rejected` row got swept into "mismatch" even though
the real issue there was simply "unknown," not "inconsistent."

**Corrected check** — restricted to rows where `qty_rejected` was actually known:
```python
known_reject = df[df['qty_rejected'].notna()]
real_mismatch = known_reject[known_reject['qty_received'] + known_reject['qty_rejected'] != known_reject['order_qty']]
# 333 genuine mismatches
```
Example: `order_qty=313, qty_received=0, qty_rejected=0` — 313 units ordered, with the
record confidently claiming 0 accepted and 0 rejected. Unlike `unit_cost`'s outliers, there
is **no candidate correction** here — no sign to flip, no plausible single-digit typo to
guess at. The data simply doesn't account for where the ordered quantity went.

**Decision**: don't guess, don't delete, don't silently leave it looking normal — flag it.
Added a new `qty_mismatch_flag` column, combining both root causes (a genuine arithmetic
mismatch, and simply not knowing `qty_rejected` at all) into one honest "this row's quantity
data isn't trustworthy" signal, without altering the original values:
```python
df['qty_mismatch_flag'] = False
df.loc[(df['qty_rejected'].notna()) &
       (df['qty_received'] + df['qty_rejected'] != df['order_qty']), 'qty_mismatch_flag'] = True
df.loc[df['qty_rejected'].isna(), 'qty_mismatch_flag'] = True
# 2,230 rows flagged total (333 genuine mismatches + missing-qty_rejected rows,
# read directly from the final column state, not manually summed across steps --
# see the double-counting mistake below)
```

**A double-counting mistake caught along the way**: after running the two `.loc[...] = True`
lines above (which already combine into one final column state), manually adding the
previously-reported 333 to the column's new total produced 2,563 — inflated, because the
333 mismatched rows were already included inside the updated column's count. The fix:
always read the current state directly (`df['qty_mismatch_flag'].sum()`), never
hand-add numbers from earlier, separate print statements — those earlier numbers may already
be folded into a later one.

### `rejection_reason` — case + whitespace, one extra character checked

Same shape as `category`/`channel`: 16 raw variants of 4 real reasons. Also checked that the
`/` in `'Expired/near-expiry'` wouldn't break `.str.title()` the way hyphens needed checking
before — confirmed it renders correctly as `'Expired/Near-Expiry'`.
```python
df['rejection_reason'] = df['rejection_reason'].str.strip().str.title()
```

### Lessons

- A duplicate check on an ID column can fail to find *real* duplicates if some other column
  (like a mixed-format date) makes otherwise-identical rows look string-different. Fix
  representational inconsistencies in other columns first, then re-run the duplicate check
  — don't assume a clean-looking duplicate count means there are no duplicates.
- Some data-quality problems span multiple columns and have no single-column detection
  path — these need a purpose-built check reasoned out for that specific relationship, not
  a generic script.
- `NaN` propagates through arithmetic and always fails equality comparisons — a naive
  mismatch check across columns needs to explicitly exclude or separately handle rows with
  missing values in either operand, or "missing" and "genuinely inconsistent" get conflated
  into one misleading count.
- Not every numeric inconsistency has a fixable answer. When there's no verifiable
  correction (no sign to flip, no confident interpolation, no safe guess), the honest move
  is to flag the row as unreliable in a new column — not delete it, not silently leave it
  looking trustworthy, and not fabricate a number that resolves the arithmetic.
- When a column's value has been updated across multiple sequential operations, always
  re-read the current total from the dataframe itself rather than mentally tracking and
  summing counts from earlier, separate print statements — the values from an earlier step
  may already be included in a later one, and manually re-adding them double-counts.

---

## 💳 `sales_transactions.csv`

The largest table (~290,700 rows) and the most issue-dense — this is where every pattern
learned across the previous six tables got combined, plus two genuinely new kinds of
findings: a duplicate that needed *two* prerequisite fixes (not one), and a fully
data-verified fill value (the first "fillna(0)" in this whole cleaning project backed by
proof, not assumption).

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `customer_id`: 14,637 (5.04%); `discount_pct`: 19,869 (6.84%); `promo_id`: 285,650 (98.27%); `payment_method`: 985 (0.34%) + 1,952 hidden placeholders |
| Duplicates | 514 full-row; 2,306 `transaction_id` duplicates (real, but hidden behind *two* columns) |
| Text/category inconsistency | `transaction_date` mislabeled (date-format issue); `store_id` — real case+whitespace; `payment_method` — real case+whitespace+placeholders |
| Date integrity | 0 parse failures once fixed |
| Numeric anomalies | `quantity`: 290 negative; `unit_price`: min 0.0 (287 rows) |

### `store_id` — case+whitespace, but `.upper()` not `.title()`

Same shape of fix as `category`/`channel`, with one deliberate difference: used
`.str.strip().str.upper()` instead of `.str.title()`, because `store_id` (`ST01`, `ST02`...)
is an ID/code, not a name — the correct standard format is all-uppercase, matching how
`product_id`/`customer_id` were already found clean. `.title()` would have produced the
wrong format (`St01`).
```python
df['store_id'] = df['store_id'].str.strip().str.upper()
```
Confirmed 20 unique stores after the fix, matching the known store count.

### `payment_method` — case AND placeholder values mixed together

`.unique()` showed both a real case-inconsistency (`'CARD'`/`'Card'`/`'card'`, etc.) and two
placeholder-style values (`'Unknown'`, `'-'`) sitting alongside the legitimate categories.
Reasoned that `'Unknown'` and `'-'` carry the same *meaning* as an actual missing value
(`NaN`) — just a different appearance — so unified them before applying the case fix, the
same principle already used for inconsistent null representation elsewhere in this dataset:
```python
df['payment_method'] = df['payment_method'].replace(['Unknown', '-'], pd.NA)
df['payment_method'] = df['payment_method'].str.strip().str.title()
```
Verified the missing count after merging (2,937) exactly equaled the original 985 (`NaN`)
plus 1,952 (placeholders) — confirming no rows were double-counted or lost.

### `transaction_id` — a real duplicate hidden behind TWO columns this time

`nunique()` (288,363) vs `len(df)` (290,669) confirmed a genuine 2,306-row gap — same
diagnostic used on `po_id`. But inspecting the duplicate pairs directly showed something new:
some pairs differed only by date format (the now-familiar `po_id` pattern), but others *also*
differed in `payment_method` casing (e.g. `'Cash'` vs `'cash'`) on top of that. A single
prerequisite fix (dates alone) would not have been enough this time — both `transaction_date`
and `payment_method` needed fixing before the rows became truly string-identical.
```python
df['transaction_date'] = pd.to_datetime(df['transaction_date'], format='mixed', dayfirst=True, errors='coerce')
# payment_method fixed as above, BEFORE this duplicate check:
df = df.drop_duplicates(subset=['transaction_id'], keep='first')
```
Row count dropped from 290,669 to 288,363 — exactly matching the gap identified up front.
The separately-flagged "514 full identical rows" turned out to already be a subset of these
same duplicates — confirmed by re-checking `df.duplicated().sum()` after the dedup, which
came back 0, so no separate action was needed for that count.

### `unit_price` = 0 (287 rows) — recoverable this time, but not attempted

Same defect shape as `products.csv`'s `unit_price == 0`, but this table had extra
information available: `total_amount` and `quantity` were both intact and consistent
(`total_amount` was a plausible price × quantity, not 0), meaning `unit_price` could in
principle be recovered via `total_amount / quantity`. Checked whether that formula would be
safe to apply uniformly first:
```python
zero_price = df[df['unit_price'] == 0]
zero_price['discount_pct'].value_counts(dropna=False)
# 0.0: 257, NaN: 26, plus 4 rows with 11/14/20/25% discount
```
Only 257 of 287 rows had zero discount (where `unit_price = total_amount / quantity` holds
exactly); the other 30 either had unknown discount or a real discount percentage, which
changes the formula and introduces ambiguity about whether the discount applies before or
after the stored price. Rather than writing two different formulas for a 257-vs-30 split,
chose the simpler, uniformly-safe option: set all 287 to `NaN`, consistent with the
`unit_price`/`unit_cost` guess-vs-verified-fix principle from `products.csv` — a fix that
works for most but not all of a group isn't a single verified fix, it's still a judgment call.
```python
df.loc[df['unit_price'] == 0, 'unit_price'] = pd.NA
```

### `quantity` negative (290 rows) — same verification method as before

```python
df.loc[df['quantity'] < 0, 'quantity'].abs().describe()   # median 1, mean ~1.89
df.loc[df['quantity'] >= 0, 'quantity'].describe()         # median 1, mean ~2.00
```
Medians matched closely (means were close too); the large difference in `max` (7 vs 695)
was recognized as a sample-size artifact (288 rows vs 288,075), not a red flag — a much
larger group is simply more likely to contain rare extreme values. Consistent with a
sign-flip error.
```python
df['quantity'] = df['quantity'].abs()
```

### `promo_id` missing (98.27%) — verified as the *normal* case, not a defect

The high percentage looked alarming at first glance, but reasoning about the business
context (~190 promotion campaigns, each lasting only days, against ~290K transactions
spread across 2 years) suggested most purchases should NOT be tied to a promotion. Verified
numerically:
```python
df['promo_id'].notna().mean() * 100   # 1.73%
```
1.73% + 98.27% = 100% — confirms the "missing" values are the expected majority case
(ordinary, non-promotional purchases), not a data quality problem. Left untouched.

### `discount_pct` missing (19,869) — the first genuinely data-verified fillna(0) in this project

Investigated whether `discount_pct` missingness related to `promo_id` before deciding
anything, following the same "check for context/contradiction first" standard used
throughout:
```python
no_promo = df[df['promo_id'].isna()]['discount_pct'].value_counts(dropna=False)
# 0.0: 264,001   NaN: 19,384
has_promo = df[df['promo_id'].notna()]['discount_pct'].describe()
# count: 4628 (no NaNs at all), min 10, max 45
```
This proved, rather than assumed, that discounts only ever apply during an active
promotion — every promotional transaction had a real, non-zero percentage, and the
overwhelming majority of non-promotional transactions already had `discount_pct = 0`. That
justified filling the 19,384 missing values *within the no-promo group only* with `0`,
scoped narrowly so it could never touch a row that does have a promotion:
```python
df.loc[df['promo_id'].isna(), 'discount_pct'] = df.loc[df['promo_id'].isna(), 'discount_pct'].fillna(0)
```
This is different from every earlier missing-value decision in this project (`region`,
`actual_delivery_date`, `qty_rejected`) — those were all "leave as NaN" because no fill
value could be verified. Here, the business rule was directly demonstrated by the data
itself before filling, which is what made `0` a justified value rather than a guess.

**A genuine contradiction found in the remaining 350 missing values**: after the fix above,
350 rows still had `discount_pct = NaN` — but every one of them had a `promo_id` present.
That breaks the very rule just proven (a promotional transaction should always have a real
discount percentage). Since there's no way to recover *which* percentage was intended (could
plausibly be any value in the observed 10-45% range), this was left as `NaN` rather than
guessed — but documented explicitly as a landmine: **do not blindly `fillna(0)` the whole
`discount_pct` column in any future step** — that would incorrectly zero out these 350 rows
that are known to have had a real discount.

### `customer_id` missing (14,512 after dedup) — no clean explanation found, left as-is with a downstream warning

Checked for a `payment_method` correlation (hypothesizing cash sales might be under-tracked):
```python
df[df['customer_id'].isna()]['payment_method'].value_counts(dropna=False)
# Card: 5742, Cash: 4981, Mobile Banking: 3653
```
No single payment method dominated — missingness looked evenly spread rather than tied to
one plausible cause, so no fix was attempted. **Explicitly documented downstream impact**
instead of just leaving the decision unstated: `groupby('customer_id')`-based analysis
(especially the planned Project 6 — Customer Analytics / RFM segmentation) will silently
exclude these ~5% of transactions, which could modestly understate customer-level metrics
like average revenue per customer. Aggregate, non-customer-level analysis (demand
forecasting, store/product-level sales) is unaffected.

### Lessons

- A duplicate hidden behind representational differences can depend on *more than one*
  column, not just dates — `po_id` needed one prerequisite fix (dates), `transaction_id`
  needed two (dates AND payment method casing). Always inspect the actual duplicate pairs
  directly rather than assuming the same single fix that worked on an earlier table will be
  enough here.
- A recoverable-looking formula (`unit_price = total_amount / quantity`) is only a *verified*
  fix if it holds for the whole affected group. If a formula only works cleanly for most of
  the rows (257 of 287 here) and the rest need a different, more uncertain calculation, the
  simpler and more honest choice is to treat the whole group as unrecovered rather than
  writing two different fixes for an arbitrary split.
- The safest way to justify filling a missing value with a specific number is to first prove
  the fill value from the data itself (here: showing every promotional transaction had a
  non-zero discount, and the vast majority of non-promotional ones already had zero) —
  not to assume a plausible-sounding default and apply it everywhere.
- Proving a business rule with data can also reveal violations of that same rule (the 350
  rows with a promo_id but no discount) — these are genuine contradictions, not just
  "still missing," and deserve their own explicit warning in documentation rather than being
  silently absorbed into the same fillna as the properly-explained missing values.
- Not every missing-value investigation finds a clean explanation. When none is found
  (`customer_id`), the correct move is still to leave the values untouched — but to write
  down exactly which future analyses the missingness will silently affect, rather than
  treating "no explanation found" as the end of the investigation.

---

## 💳 `sales_transactions.csv`

The largest table (~290K rows) and the richest set of findings — including a duplicate
that needed *two* prerequisite columns fixed first (not just one, as with `purchase_orders`),
and a business rule (discount only exists alongside a promotion) that was proven from the
data itself before being used to justify filling missing values with a specific number.

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `customer_id`: 14,637 (5.04%); `discount_pct`: 19,869 (6.84%); `promo_id`: 285,650 (98.27%); `payment_method`: 985 (0.34%) + 1,952 hidden placeholders |
| Duplicates | 514 full-identical rows; 2,306 `transaction_id` duplicates (real, but only detectable after two other columns were fixed) |
| Text/category inconsistency | `transaction_date` mislabeled (date-format, familiar pattern); `store_id` — real case+whitespace; `payment_method` — real case+whitespace, plus placeholder values |
| Date integrity | 0 parse failures once fixed |
| Numeric anomalies | `quantity`: 290 negative values; `unit_price`: 287 zero values |

### `store_id` — case + whitespace, but with a twist on the fix method

Same shape of mess as `category`/`channel` (20 stores written in mixed case and with
stray whitespace), but fixed with `.str.upper()` instead of `.str.title()`:
```python
df['store_id'] = df['store_id'].str.strip().str.upper()
```
`store_id` is a code (`ST01`), not a name — `.title()` would have produced the wrong
convention (`St01`), even though it "normalizes" the text just as validly in isolation.
The right generic method still depends on what kind of value the column holds.

### `payment_method` — two problems in one column, needing two different fixes

`.unique()` showed both a familiar case-inconsistency issue (`'CARD'`/`'Card'`/`'card'`) and
a new kind of issue: literal placeholder text (`'Unknown'`, `'-'`) alongside real `NaN`,
all meaning the same thing — "we don't know the payment method" — but represented three
different ways.
```python
df['payment_method'] = df['payment_method'].replace(['Unknown', '-'], pd.NA)
df['payment_method'] = df['payment_method'].str.strip().str.title()
```
Verified the unified missing count (985 + 1,952 = 2,937) matched exactly after merging —
confirming no rows were double-counted or lost in the process.

### `transaction_id` — a real duplicate, but requiring TWO prerequisite fixes (not one)

`transaction_id` is meant to be a true primary key (`nunique()` = 288,363 vs. `len(df)` =
290,669 — a genuine 2,306-row gap, matching the report's flagged count exactly). Inspecting
duplicate pairs directly showed the same date-representation issue seen on
`purchase_orders.po_id` (`'12/02/2024'` vs `'2024-02-12'`) — but *also* a second source of
string-mismatch: `payment_method` case differences (`'Cash'` vs `'cash'`, `'CARD'` vs
`'Card'`) on otherwise-identical rows.

**This meant the duplicate check would still fail even after fixing dates alone** — a pair
differing only in `payment_method` casing would still look string-different. Both columns
had to be normalized first:
```python
df['transaction_date'] = pd.to_datetime(df['transaction_date'], format='mixed', dayfirst=True, errors='coerce')
# payment_method fix (above) also applied before this point
df = df.drop_duplicates(subset=['transaction_id'], keep='first')
```
Row count dropped from 290,669 to 288,363 — exactly matching the earlier `nunique()`
calculation — and 0 duplicates remained, confirming no third column was still causing
mismatches.

### `unit_price` = 0 (287 rows) — reverse-calculation was possible, but too fragile to use safely

Unlike `products.csv`'s zero price, this table has `quantity` and `total_amount` alongside
`unit_price`, which in principle allows `unit_price = total_amount / quantity` to recover
the real price mathematically — genuinely more information than was available on
`products.csv`.

Checked `discount_pct` for the 287 affected rows before trusting that formula, since a
discount changes the math: 257 rows had `discount_pct = 0` (simple division would be exact),
26 had `discount_pct = NaN` (unknown), and 4 had a real discount (a different, more complex
formula would be needed, and it's unclear whether the discount applies before or after the
stored price). Rather than build three different formulas for a 287-row problem — with the
4-row discounted case resting on an assumption about calculation order that couldn't be
verified — the simpler and safer choice was made: set all 287 to `NaN`.
```python
df.loc[df['unit_price'] == 0, 'unit_price'] = pd.NA
```
This is consistent with the `products.csv` `unit_price`/`unit_cost` principle: a fix is only
applied when it's verifiable across the board, not just plausible for most of the rows.

### `quantity` negative values (290) — verified via magnitude, same method as before

```python
df.loc[df['quantity'] < 0, 'quantity'].abs().describe()   # mean ~1.89, median 1.0
df.loc[df['quantity'] >= 0, 'quantity'].describe()          # mean ~2.00, median 1.0
```
Means and medians matched closely; the large gap in `max` (7 vs 695) was recognized as a
sample-size artifact (288 negative rows vs. 288,075 positive rows — a much bigger sample is
simply more likely to contain rare large outliers), not evidence against the sign-flip
theory. Fixed with `.abs()`.

### `promo_id` missing (98.27%) — verified as the *normal* case, not a defect

With ~190 promotion campaigns (each lasting only days) spread across ~290K transactions
over 2 years, the overwhelming majority of purchases should have no associated promotion —
confirmed directly (`notna().mean()` = 1.73%, the exact complement of the reported missing
rate). Left untouched; this is a legitimate optional foreign key, not missing data.

### `discount_pct` — a business rule proven from the data, then used to justify two very
### different decisions on two subsets of the same missing values

This was the most involved finding on this table. The hypothesis (discounts only exist
alongside a promotion) was checked directly by comparing `discount_pct` between the
promo and no-promo groups:
```python
df[df['promo_id'].isna()]['discount_pct'].value_counts(dropna=False)
# 0.0: 264,001   NaN: 19,384
df[df['promo_id'].notna()]['discount_pct'].describe()
# count 4,628, min 10.0, max 45.0 -- zero NaNs, zero zeros
```
Every promo-linked transaction had a real, non-zero discount; the vast majority of
non-promo transactions had exactly `0`. This wasn't just a plausible assumption — the data
itself confirmed the rule with no exceptions on the promo side.

**Consequence for the ~19,384 missing values in the no-promo group**: since the rule holds
with no counterexamples, filling these with `0` is a *verified* fix, not a guess — the first
time in this dataset that a specific fill value (rather than `NaN` or an interpolation) was
justified this way.
```python
df.loc[df['promo_id'].isna(), 'discount_pct'] = df.loc[df['promo_id'].isna(), 'discount_pct'].fillna(0)
```
Scoped deliberately to only the no-promo rows (`.loc[df['promo_id'].isna(), ...]`) rather
than a blanket `fillna(0)` on the whole column — applying `0` to a promo-linked row would
have been wrong.

**But 350 rows broke the pattern**: after the fix above, 350 rows still had
`discount_pct` missing — and checking them showed every single one *did* have a `promo_id`.
This is the inverse of the pattern just proven (a promotion exists, but its discount amount
is unknown) — a genuine contradiction, not covered by the just-established rule. Filling
these with `0` would directly contradict the very evidence used to justify filling the
*other* group with `0`. No verified number exists to fill them with (the real value could
plausibly be anywhere in the promo group's observed 10-45% range), so they were left as
`NaN` — with an explicit warning recorded here: **do not blanket-`fillna(0)` this column in
any future analysis** — 350 rows would silently get an incorrect `0%` discount despite
genuinely having an active promotion.

### `customer_id` missing (14,512 after dedup) — legitimate, but with a real downstream cost

Checked against `payment_method` for a pattern (hypothesis: anonymous cash sales) — not
confirmed; missingness was spread fairly evenly across Card (5,742), Cash (4,981), and
Mobile Banking (3,653), not concentrated in one method. No contradiction with any other
column, and no verifiable way to recover a real customer ID, so left untouched.

**Unlike `region`, this one has a concrete, foreseeable downstream impact worth flagging
explicitly**: any customer-level analysis (Project 6 — RFM segmentation, churn) will
silently exclude these ~5% of transactions from `groupby('customer_id')`-based aggregation,
since pandas drops `NaN` group keys by default. Total revenue/quantity figures are
unaffected (the rows are still present), but customer-level metrics (average revenue per
customer, purchase frequency) will be based on a slightly incomplete customer population.
This is a known dataset limitation to account for when reaching Project 6, not a defect to
fix now.

### Full identical rows (514)

Verified as already resolved by the `transaction_id` dedup above (`df.duplicated().sum()`
returned `0` after that fix) — not a separate, remaining issue.

### Lessons

- The number of prerequisite columns needed before a duplicate check works correctly isn't
  fixed — `po_id` needed one (dates), `transaction_id` needed two (dates AND payment
  method). Always inspect actual duplicate *pairs* directly rather than assuming a single
  fix resolved everything; a remaining nonzero duplicate count after one fix is a sign
  something else is still causing string mismatches.
- The right generic text-cleaning method depends on what the column represents, not just
  whether it "looks like a case problem" — an ID code wants `.upper()`, a name/category
  wants `.title()`.
- More available context (like `total_amount` and `quantity` alongside a broken
  `unit_price`) doesn't automatically mean a value is safely recoverable — if applying the
  reverse formula correctly depends on an assumption that can't be verified for a meaningful
  chunk of the affected rows (here, discount order-of-operations for 4 of 287 rows), the
  simpler, honest choice (`NaN`) can still be the right one over a more "clever" fix.
  Recoverability is about certainty for *all* affected rows, not most of them.
- A hypothesis about *why* values are missing should be tested against the data before it's
  used to justify a fix — the discount/promotion relationship wasn't assumed, it was proven
  with zero counterexamples on one side of the relationship. That's what made filling with
  `0` a justified correction rather than a guess.
- Proving a rule holds for one subset of missing values doesn't mean it applies to the
  *rest* of the missing values in the same column — the 350 promo-linked-but-discount-missing
  rows are missing for a different, contradictory reason, and needed a different decision
  (and an explicit warning against ever blanket-filling that column) rather than being swept
  into the same fix.
- A "leave it untouched" decision on a missing-value column still needs its downstream
  impact spelled out explicitly, not just left implicit — future analysis on a different
  project (here, customer-level aggregation) can be silently affected by a decision made
  while cleaning a different table.

---

## 🚛 `shipments.csv`

The table where the most important finding wasn't flagged by `investigate.py` at all —
a unit-mismatch bug hiding inside numbers that looked completely normal on their own.

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `actual_arrival_date`: 25 (0.28%); `shipment_cost`: 462 (5.10%) |
| Duplicates | 4 full-identical rows; 89 `shipment_id` duplicates (real, representational -- same root cause as `po_id`/`transaction_id`) |
| Text/category inconsistency | `shipment_status` flagged, but a false positive (hyphenated values already correct); date columns mislabeled (familiar mixed-format pattern) |
| Date integrity | 0 parse failures once fixed |
| Numeric anomalies | none flagged by the generic min/max/negative check -- but a real issue existed anyway (see below) |

### `shipment_status` — a false positive with data that was already clean

`.unique()` showed `['Delayed', 'On-time', 'Lost', 'Damaged', 'In-Transit']` -- already
consistent, no fix needed. The "Mixed Case Styles" flag was the same `.istitle()`
limitation seen on `Walk-in`/`In-Store`: hyphenated values (`On-time`, `In-Transit`) don't
satisfy Python's strict title-case check even when they're correctly formatted. A useful
reminder that a flag from `investigate.py` should always be verified against `.unique()`
before assuming a fix is needed -- sometimes the answer is "nothing to do here."

### `shipment_id` duplicates (89) — needed all 3 date columns fixed first

Same shape as `po_id`/`transaction_id`: `nunique()` (8,968) vs. `len(df)` (9,057) showed
an 89-row gap matching the report exactly. Inspecting duplicate pairs directly showed every
other column identical except date representation across all three date columns
(`dispatch_date`, `expected_arrival_date`, `actual_arrival_date`). Fixed all three with
`pd.to_datetime(..., dayfirst=True)` before running `drop_duplicates(subset=['shipment_id'])`
-- row count dropped from 9,057 to 8,968 exactly as predicted, with 0 duplicates remaining.

### `actual_arrival_date` missing (25) — verified consistent with `shipment_status`

All 25 missing rows had `shipment_status == 'In-Transit'` (100%, no exceptions) --
identical reasoning to `purchase_orders.actual_delivery_date`/`po_status == 'Pending'`: a
shipment still in transit has no arrival date because it hasn't arrived. Left untouched.

### `distance_km` — a mixed-unit bug entirely invisible to the generic numeric check

This is the most important finding on this table. `investigate.py`'s Section 6 flagged
nothing for `distance_km` -- both min (5.0) and max (417.6) looked like completely
reasonable distances. But a value written in miles instead of km looks just as "normal" as
one written correctly -- unit confusion doesn't produce an outlier, it produces a
plausible-looking wrong number. No generic script check catches this; it requires domain
reasoning about what the column *means*.

**Detection approach**: since a warehouse and a store are both fixed physical locations,
the distance between any specific (warehouse, store) pair should always be the same number,
across every shipment on that route:
```python
route_stats = df.groupby(['warehouse_id', 'store_id'])['distance_km'].agg(['min', 'max', 'nunique']).reset_index()
route_stats['ratio'] = route_stats['max'] / route_stats['min']
```
This surfaced two very different patterns:
- Some routes had `nunique` in the hundreds (e.g. 209, 253) with no consistent ratio --
  legitimate real-world variation (different paths/detours), not a data error.
- 42 routes had *exactly* 2 distinct distance values, with a ratio landing within 0.5% of
  **1.609** every time -- the km-to-mile conversion factor. That level of consistency across
  42 independent routes rules out coincidence.

**Recovering the correct value**: for each flagged route, the smaller of the two values is
the one written in miles (a mile is always a smaller number than the equivalent km), so the
larger value is the real distance:
```python
for _, route in suspicious_routes.iterrows():
    wh, st, correct_km = route['warehouse_id'], route['store_id'], route['max']
    mask = (df['warehouse_id']==wh) & (df['store_id']==st) & (df['distance_km']==route['min'])
    df.loc[mask, 'distance_km'] = correct_km
```
385 rows fixed. Re-checked afterward and found 15 routes still showing more than one
distinct value -- verified these were the same kind of legitimate high-variance routes
identified above (ratios nowhere near 1.609, `nunique` in the hundreds), confirming the fix
was complete and hadn't missed any genuine mixed-unit cases.

### `store_id` = 'ST99' (33 rows) — an orphan foreign key, recovery attempted and rejected

While re-checking the routes above, a `store_id` value ('ST99') appeared that doesn't exist
in the 20 real stores (`ST01`-`ST20`) -- an orphan foreign key. Attempted to recover the
real store from `distance_km`, using the same route-distance-consistency logic as the
mixed-unit fix: for one `ST99` row (`W03`, `distance_km=21.1`), compared against every valid
`W03` route's average distance. Four different stores (`ST01`, `ST08`, `ST04`, `ST07`) all
had average distances within about 1 unit of 21.1 -- no single best match, just several
similarly-plausible candidates. Unlike the mixed-unit case (where exactly one interpretation
fit with high precision), guessing among four near-equal options isn't a verified
correction, it's a coin flip dressed up as a calculation.

**Decision**: flagged rather than corrected or deleted, consistent with the
`purchase_orders.qty_mismatch_flag` precedent — the row stays in the dataset (its other
columns are still usable), but is marked as having an unreliable `store_id`:
```python
df['store_id_invalid_flag'] = df['store_id'] == 'ST99'
```
33 rows flagged.

### `shipment_cost` missing (462) — partial recovery considered and deliberately rejected for simplicity

Checked for a pattern against `shipment_status` first (hypothesis: still-in-transit
shipments lack a final cost) — rejected: missing rows were spread across every status
(355 On-time, 91 Delayed, 9 Damaged, 2 Lost, only 1 In-Transit), the opposite of the clean
single-status pattern seen with `actual_arrival_date`. Also checked overlap with the
`store_id_invalid_flag` rows above — only 1 row overlapped, ruling out a shared root cause.

Explored whether route-level cost consistency (`std/mean`, i.e. coefficient of variation)
could support a similar "recover from a consistent route pattern" approach used for
`distance_km`. It could have, partially — some routes had low variation (cv ~0.09-0.11,
cost fairly predictable) — but overall variation across all 63 routes ranged from 0.09 to
1.15, meaning a single fill strategy (route average) would have been safe for some routes
and badly wrong for others. Rather than build a per-route threshold to decide which routes
were "safe enough" to fill (an arbitrary judgment call, not a verified rule), all 462 rows
were left as `NaN` for a simpler, more defensible outcome — consistent treatment across the
whole column rather than a partial fix with a hidden, hard-to-justify cutoff baked in.

### Lessons

- A numeric column with no negative values, no zeros, and a "reasonable" min/max can still
  be wrong — unit confusion (km recorded as miles) produces numbers that look completely
  plausible in isolation. This kind of error is only detectable by checking consistency
  *within* a logical grouping (here, a fixed route), not by looking at the column's overall
  distribution.
- A precise, repeated ratio (1.609 across 42 independent routes) is much stronger evidence
  of a systematic unit bug than a single instance would be — coincidence doesn't produce
  that level of consistency across unrelated data points.
- The same "check for a consistent group pattern" technique can both *fix* an issue (distance,
  where one route had exactly one plausible correct value) and *fail to justify a fix*
  (the orphan store, where four routes were all similarly plausible) — the technique itself
  doesn't guarantee a usable answer; the number of near-equally-good candidates does.
- When a recovery approach could technically work for part of a missing-value problem (some
  routes' shipment costs were consistent enough to estimate) but not all of it, introducing
  a threshold to split "recoverable" from "not recoverable" adds a new, unverified judgment
  call of its own. Sometimes the simpler, uniform decision (leave everything as `NaN`) is
  more defensible than a partially-clever one.

---

## 🏬 `stores.csv`

A small table (21 rows) with a quick but genuinely instructive apostrophe-related
exception, and otherwise a set of familiar, fast fixes.

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `manager_name`: 1 (4.76%) |
| Duplicates | 0 full-identical rows flagged, but 1 `store_id` duplicate |
| Text/category inconsistency | `city` — real case+whitespace issue, plus one apostrophe exception; `opening_date` mislabeled (familiar date-format pattern) |
| Date integrity | 0 parse failures once fixed |
| Numeric anomalies | none (`store_size_sqft` min/max both reasonable) |

### `city` — case + whitespace, plus a new kind of `SwiftHaul`-style exception

`.unique()` showed the familiar case/whitespace mess (`'chattogram'`, `'NARAYANGANJ'`,
`' Dhaka '`), but also `"cox's bazar"` / `"Cox's Bazar"` — a city name containing an
apostrophe. Before applying the generic fix blindly, tested it on a small sample first:
```python
pd.Series(["cox's bazar", "Cox's Bazar", "COX'S BAZAR"]).str.strip().str.title()
# -> all three become "Cox'S Bazar"
```
Python's `.title()` treats an apostrophe as a word boundary, capitalizing the letter right
after it -- turning a correctly-formatted name into a broken one, the same failure mode as
`SwiftHaul`/`carrier_name`, just triggered by a different character. Fixed with the generic
method plus a targeted manual correction for the one broken case:
```python
df['city'] = df['city'].str.strip().str.title()
df['city'] = df['city'].replace("Cox'S Bazar", "Cox's Bazar")
```

### `opening_date` — familiar mixed-date-format pattern

Same as every other date column in this dataset: three formats mixed together, fixed with
`pd.to_datetime(..., format='mixed', dayfirst=True)`. 0 parse failures.

### `store_id` duplicate (1) — simple, fully identical

Unlike `po_id`/`shipment_id`/`transaction_id`, this single duplicate pair was already
byte-for-byte identical in every column even before the date fix (both rows already showed
the same date representation) -- a straightforward `.drop_duplicates(subset=['store_id'])`
was all that was needed, no prerequisite fix required first.

### `manager_name` missing (1)

Checked the row for context (store type, city, opening date) -- no contradiction with any
other column, no clear explanatory pattern (e.g. the store isn't unusually newly-opened
compared to others in the dataset). Left untouched, same reasoning as `customers.region`.

### Lessons

- The `SwiftHaul`-style "generic text-cleaning method breaks a legitimately special value"
  problem isn't limited to internal capitals or hyphens -- an apostrophe triggers the same
  failure mode in `.title()`. The lesson generalizes: any punctuation inside a text value is
  worth testing against the cleaning method on a small sample before trusting it at scale,
  not just hyphens and capitals specifically.
- Not every duplicate needs a prerequisite fix first -- some are simple and fully identical
  from the start. The `po_id`/`shipment_id`/`transaction_id` pattern (representational
  duplicates hidden by date-format differences) is common in this dataset but not universal;
  always check what a duplicate pair actually looks like before assuming which kind it is.

---

## 🏬 `stores.csv`

A small table (21 rows) that still produced a genuine "generic fix breaks legitimate data"
case, the same family of issue as `carrier_name`'s `SwiftHaul`, but caused by a different
character this time.

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `manager_name`: 1 (4.76%) |
| Duplicates | 1 `store_id` duplicate |
| Text/category inconsistency | `city` — real case+whitespace issue, with an apostrophe exception; `opening_date` mislabeled (familiar date-format pattern) |
| Date integrity | 0 parse failures once fixed |
| Numeric anomalies | none (`store_size_sqft` min/max both plausible) |

### `city` — case+whitespace fix, except for one name with an apostrophe

`.unique()` showed the usual mixed-case/whitespace mess across city names, but one value —
`Cox's Bazar` — has an apostrophe. Before applying the generic fix blindly, tested it on a
small sample first (the same caution used for `carrier_name`):
```python
pd.Series(["cox's bazar", "Cox's Bazar"]).str.strip().str.title()
# -> 'Cox'S Bazar' (wrong -- capitalizes the letter after the apostrophe)
```
Confirmed the same risk seen with `SwiftHaul`: a blanket `.title()` would silently corrupt
a legitimately-formatted name. With only one affected value in a 21-row table, applied the
generic fix to the whole column and then explicitly corrected just that one case, rather
than building special apostrophe-handling logic for a single instance:
```python
df['city'] = df['city'].str.strip().str.title()
df['city'] = df['city'].replace("Cox'S Bazar", "Cox's Bazar")
```

### `opening_date` — the familiar mixed-format issue

Same pattern and same fix as every other date column in this dataset:
```python
df['opening_date'] = pd.to_datetime(df['opening_date'], format='mixed', dayfirst=True, errors='coerce')
```

### `store_id` duplicate (1 row) — a real, fully identical duplicate

Unlike the representational duplicates on larger tables (which needed date columns fixed
first), this one was a straightforward exact match across every column, including the
already-fixed `opening_date` -- `ST03` appeared twice with identical data. Removed directly:
```python
df = df.drop_duplicates(subset=['store_id'], keep='first')
```

### `manager_name` missing (1 row)

Checked the row's other columns for any explanatory pattern (a very recently opened store,
an unusual store type) -- found nothing distinguishing it from other stores. A single,
unremarkable missing value with no verifiable explanation or fix -- left untouched, same
category as `customers.region`.

### Lessons

- Even in a 21-row table, the same class of "generic text fix breaks a legitimate value"
  issue can appear -- this time from an apostrophe rather than an internal capital letter
  or a hyphen. The lesson from `carrier_name` (test the generic fix on a small sample before
  trusting it) applies regardless of table size.
- For a single affected value in a small column, a targeted override after the generic fix
  is simpler and clearer than writing conditional logic to detect and handle the special
  character during the fix itself.

---

## 🤝 `suppliers.csv`

A straightforward table -- every issue matched a pattern already established on earlier
tables, with no new surprises. Included here mainly to confirm the established methods
generalize cleanly once the underlying patterns are recognized.

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `payment_terms_days`: 5 (11.11%) |
| Duplicates | none |
| Text/category inconsistency | `region` — familiar case+whitespace issue, no exceptions this time; `contract_start_date` mislabeled (familiar date-format pattern) |
| Date integrity | 0 parse failures once fixed |
| Numeric anomalies | none (`payment_terms_days`, `base_lead_time_days` both within plausible ranges) |

### `region` — case + whitespace, no exceptions this time

Unlike `city` (`Cox's Bazar`) or `carrier_name` (`SwiftHaul`), `.unique()` showed no
apostrophes, hyphens, or internal capitals to worry about -- just the standard 6 regions in
mixed case with stray whitespace. Fixed directly with no need for a sample test first:
```python
df['region'] = df['region'].str.strip().str.title()
```

### `contract_start_date` — the familiar mixed-format issue

```python
df['contract_start_date'] = pd.to_datetime(df['contract_start_date'], format='mixed', dayfirst=True, errors='coerce')
```

### `payment_terms_days` missing (5) — no pattern found

Checked the 5 affected suppliers' other columns for anything explanatory: region (spread
across Dhaka, Khulna x2, Barishal, Rajshahi -- no concentration), contract start date
(spanning 2018-2024 -- ruling out "too new to have terms set yet" as an explanation, since
some are old contracts), and `base_lead_time_days` (5-17, well within the dataset's overall
3-20 range -- no contradiction). No recoverable pattern -- left untouched.

### Lessons

- Not every table produces a new kind of finding -- confirming that a table's issues match
  already-established patterns (and applying the same fixes with the same reasoning) is
  itself useful, not wasted effort. It's evidence the earlier decisions generalize, not
  just one-off fixes for one table's specific data.

---

## 🤝 `suppliers.csv`

A short, mostly straightforward table -- no surprises, no false positives to catch, just
the familiar patterns applied cleanly.

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `payment_terms_days`: 5 (11.11%) |
| Duplicates | none |
| Text/category inconsistency | `region` — real case+whitespace issue; `contract_start_date` mislabeled (familiar date-format pattern) |
| Date integrity | 0 parse failures once fixed |
| Numeric anomalies | none (`payment_terms_days` and `base_lead_time_days` both had plausible ranges) |

### `region` — straightforward case+whitespace fix

`.unique()` showed no legitimate exceptions (no apostrophes, hyphens, or internal capitals
this time) -- 6 real regions written in mixed case with some stray whitespace. Fixed
directly:
```python
df['region'] = df['region'].str.strip().str.title()
```
Confirmed 6 unique values remained afterward, matching the dataset's known region count.

### `contract_start_date` — the familiar mixed-format fix

```python
df['contract_start_date'] = pd.to_datetime(df['contract_start_date'], format='mixed', dayfirst=True, errors='coerce')
```

### `payment_terms_days` missing (5) — no pattern found, left untouched

Checked the 5 affected suppliers' other columns (region, contract start date,
base_lead_time_days) for any pattern that might explain or justify a fix. Contract start
dates ranged from 2018 to 2024 -- ruling out "newly onboarded supplier hasn't had terms set
yet" as an explanation, since some of the affected suppliers had contracts dating back
years. Regions were spread across four different areas, not concentrated in one.
`base_lead_time_days` values were all within the dataset's normal range, no contradiction
there either. With no pattern to justify any specific fill value, left as `NaN` -- same
category as `stores.manager_name`.

### Lessons

- Not every table produces a false positive or a tricky edge case -- this one confirmed
  that the by-now-familiar patterns (case+whitespace cleanup, mixed-date-format fix, "check
  for a pattern before leaving a missing value untouched") generalize correctly to a table
  with no special complications, rather than only working by coincidence on the earlier,
  messier tables.

---

## 🏭 `warehouses.csv`

The last table (only 3 rows) — small, but still ended with an honest "no verified recovery
exists" call, a fitting note to close the series on.

### Investigation summary

| Check | Result |
|---|---|
| Missing values | `capacity_units`: 1 (33.33%) |
| Duplicates | none |
| Text/category inconsistency | `operational_since` mislabeled (familiar date-format pattern) |
| Date integrity | 0 parse failures once fixed |
| Numeric anomalies | none |

### `operational_since` — the familiar mixed-format fix

```python
df['operational_since'] = pd.to_datetime(df['operational_since'], format='mixed', dayfirst=True, errors='coerce')
```

### `capacity_units` missing (1 of 3 rows) — no recovery possible, left untouched

With only 3 warehouses total, there's no meaningful pattern, trend, or related column to
recover a missing capacity from — unlike `inventory_snapshots.stock_qty`, there's no
time-series to interpolate (each warehouse is a single, independent physical entity, not a
sequence of related observations), and `region`/`operational_since` give no numeric signal
about capacity. Left as `NaN`, same category as `stores.manager_name` and
`suppliers.payment_terms_days`.

### Lessons

- Table size doesn't change the reasoning process — even with just 3 rows and 2 issues, the
  same discipline applied: verify the date-format flag rather than assume, and check
  whether a missing value has any recoverable signal before deciding to leave it untouched.
  A small table isn't a reason to skip verification.

---

## Series summary — all 11 tables

Every table in this dataset has now been investigated and cleaned. Across the series:

- **3 detection false positives** were caught before being acted on: foreign-key columns
  misflagged as "duplicates" by a single-column check (recurring on almost every table),
  date columns misflagged as "case inconsistency" by a checker meant for category text, and
  already-correct values (`SwiftHaul`, `Walk-in`, `In-Store`, `Cox's Bazar`) flagged by
  Python's strict `.istitle()`/`.isupper()`.
- **3 "generic fix would have broken correct data" cases** were caught before applying a
  blind transformation: `carrier_name` (internal capital), `channel`/`payment_method`
  (hyphens, verified safe), and `stores.city` (apostrophe, verified unsafe and fixed with a
  targeted override).
- **2 duplicate-detection dependencies** were discovered: `purchase_orders.po_id` needed
  date columns fixed first; `sales_transactions.transaction_id` needed both date columns
  AND `payment_method` fixed first — duplicates can hide behind more than one
  inconsistently-formatted column at once.
- **1 completely invisible-to-automation issue** was found only through domain reasoning:
  `shipments.distance_km`'s mixed km/miles values, detected via route-level consistency
  checking rather than any single-column statistical check.
- **2 orphan foreign keys** (`shipments.store_id == 'ST99'`, and the cross-column
  `qty_mismatch_flag` case in `purchase_orders`) were flagged rather than guessed at, after
  recovery attempts were tried and found to have no single verified answer.
- **1 business rule was proven from the data itself** (`sales_transactions`: no promotion
  means no discount) before being used to justify a specific fill value — the only case in
  this dataset where a missing value was filled with a non-`NaN`, non-interpolated number
  based on evidence rather than a guess.
- **Recurring principle across every table**: a fix is only applied when it's verifiable —
  mathematically certain (sign flips), proven by the data (the discount rule), or
  unambiguous in context (`Pending`/`In-Transit` status explaining a missing date). Where no
  verified fix existed, values were left as `NaN` or flagged, never guessed.

# Investigation: Missing NORAD IDs 38752 and 38753

## Summary

NORAD IDs **38752** (Radiation Belt Storm Probe A / RBSP A / Van Allen Probe A) and **38753** (Radiation Belt Storm Probe B / RBSP B / Van Allen Probe B) are **NOT** in the database dataset.

## What These Satellites Are

- **38752**: Radiation Belt Storm Probe A (RBSP A), launched 2012 Aug 30, HEO orbit
- **38753**: Radiation Belt Storm Probe B (RBSP B), launched 2012 Aug 30, HEO orbit
- Both were NASA science missions studying Earth's Van Allen radiation belts
- Both were eventually decommissioned (GCAT shows DDate: 2012 Nov 9 and Status: N)

These entries ARE present in `gcat_satcat.tsv` (lines 38754–38755 in that file).

## Root Cause Analysis

The satellites are absent from all data sources used to populate the database:

### 1. Kaggle/CelesTrak Catalog (Primary Source)
- The database is populated primarily from the Kaggle catalog (`scripts/import/import_kaggle_catalog.py`)
- CelesTrak's current catalog only includes **currently active or recently tracked** satellites
- RBSP A/B were decommissioned by 2019 and are no longer in active TLE tracking catalogs
- **Result**: Not imported from this source

### 2. UNOOSA Registry (`data/unoosa_registry.csv` / `unoosa_registry_with_norad.csv`)
- No entries for 38752, 38753, "RBSP", "Radiation Belt", or "Van Allen" exist in the UNOOSA data
- NASA did not register these spacecraft with the UN UNOOSA registry (or registration is missing from the dataset)
- **Result**: Not imported from this source

### 3. GCAT Import (`scripts/import/import_gcat_launches.py`)
- This script reads `gcat_satcat.tsv` which DOES contain 38752 and 38753
- **However**, the import applies a strict cutoff date filter:
  ```python
  def import_gcat_launches(tsv_path, cutoff_date="2025-09-13", dry_run=False):
  ```
  ```python
  if not is_after_date(launch_date, cutoff_date):
      skipped_old += 1
      continue
  ```
- The cutoff date is **2025-09-13**, meaning only satellites launched after that date are imported
- RBSP A/B launched in **2012** — filtered out
- **Result**: Present in source file but skipped by the date filter

## Affected Components

- `scripts/import/import_gcat_launches.py` — `cutoff_date` default of `"2025-09-13"` prevents historical satellites from being imported via GCAT
- Kaggle/CelesTrak catalog — source data doesn't include decommissioned satellites
- UNOOSA registry — these satellites are not registered

## Proposed Solution

To add RBSP A/B and other decommissioned/historical satellites to the dataset, one or more of these approaches can be used:

1. **Lower the GCAT cutoff date** — Change `cutoff_date` default in `import_gcat_launches` (e.g., to `"1957-01-01"`) and re-run against ArangoDB to import historical satellites
2. **Targeted GCAT import** — Run `import_gcat_launches.py` with a custom `--cutoff-date` parameter set to an earlier date (e.g., `2010-01-01`)
3. **Manual upsert** — Directly insert the two satellites from `gcat_satcat.tsv` data into the database

**Note**: The GCAT import script targets ArangoDB (`connect_arangodb()`), not MongoDB, so the right database backend must be connected.

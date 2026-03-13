# Bug Investigation: GCAT-S57687 Status Incorrectly Shows "in orbit"

## Bug Summary

Satellite `GCAT-S57687` (NORAD 57687, "deb Artemis I", intl designator 2022-156L) has
`canonical.status = "in orbit"` and `canonical.date_of_decay_or_change = null` in the
database, but according to N2YO (and SpaceTrack), the object decayed / re-entered on
**2023-11-07**.

---

## Root Cause Analysis

### 1. Stale GCAT source data

The local `gcat_satcat.tsv` file contains an outdated snapshot of the GCAT catalog.

Raw GCAT record for S57687 (relevant columns):

| Field  | Value         |
|--------|---------------|
| DDate  | `-` (null)    |
| Status | `O` (in orbit)|

GCAT still records this object as `"O"` (operational, in orbit) with **no decay date**,
presumably because the TSV was snapshotted before the object re-entered on 2023-11-07, or
because the GCAT catalog has not yet updated this record.

### 2. Status mapping is technically correct — but wrong input

`promote_gcat_attributes.py` maps GCAT status codes to human-readable strings:

```python
GCAT_STATUS_MAP = {
    "O":  "in orbit",   # ← correct mapping for code "O"
    ...
    "R":  "decayed",
    "D":  "decayed",
    ...
}
```

The mapping itself is correct. The problem is that **the input value `"O"` is wrong** because
the GCAT dataset hasn't recorded the re-entry yet.

### 3. No SpaceTrack decay-class query

`spacetrack_service.py` only queries the `gp` (General Perturbations) class:

```
/basicspacedata/query/class/gp/NORAD_CAT_ID/{norad_id}
```

SpaceTrack's `gp` class **only returns active (currently tracked) objects**. A decayed object
returns an empty list. The current code treats this as "not found" and leaves the canonical
status untouched — it never queries SpaceTrack's `decay` class:

```
/basicspacedata/query/class/decay/NORAD_CAT_ID/{norad_id}
```

### 4. No cross-source status reconciliation

`database/transformations.py` → `update_canonical()` only allows "approved" sources to promote
to canonical: `["unoosa", "spacetrack", "celestrak", "tleapi", "kaggle"]`.

The `import_satnogs_status.py` explicitly does **not** call `update_canonical()` (SatNOGS is
unapproved). Even if SatNOGS had correct decay status, it would not flow into canonical.

`promote_gcat_attributes.py` only writes `canonical.status` when it is currently `null`
(the "fill if empty" pattern), so once "in orbit" was written, subsequent re-runs won't
correct it either.

---

## Affected Components

| File | Role |
|------|------|
| `gcat_satcat.tsv` | Source data — stale entry for NORAD 57687 |
| `scripts/import/import_gcat_bulk.py` | Imports raw GCAT status into `sources.gcat.status` |
| `scripts/maintenance/promote_gcat_attributes.py` | Promotes `sources.gcat.status` → `canonical.status` (fill-if-null, no override) |
| `api/services/spacetrack_service.py` | Only queries `gp` class — never checks SpaceTrack `decay` class |
| `database/transformations.py` | Canonical promotion logic — no decay inference |

---

## Proposed Fix

### Option A — Targeted data patch (immediate, low risk)

Write a maintenance script `scripts/maintenance/fix_decayed_status.py` that:

1. Queries the SpaceTrack `decay` class for objects whose canonical status is `"in orbit"`:
   ```
   /basicspacedata/query/class/decay/NORAD_CAT_ID/{norad_id}/format/json
   ```
2. If SpaceTrack confirms a decay event, updates the document:
   - `canonical.status` → `"decayed"`
   - `canonical.date_of_decay_or_change` → the confirmed decay date from SpaceTrack
   - Records a transformation entry in `metadata.transformations`

This directly fixes GCAT-S57687 and any other objects with the same staleness problem.

### Option B — Enrich SpaceTrack service with decay detection (systemic fix)

Extend `spacetrack_service.py` to also expose a `check_decay()` function that queries the
`decay` class. Call it from wherever status is determined (e.g., in `tle_service.py` or a
dedicated reconciliation job) so that future re-entries are caught automatically.

### Recommended approach

Implement **Option A** as the immediate fix (targeted script to repair GCAT-S57687 and similar
stale records), then follow up with **Option B** for long-term robustness.

For the implementation step, the regression test should verify that after running the fix
script, `canonical.status` becomes `"decayed"` and `canonical.date_of_decay_or_change` is
set for NORAD 57687.

---

## Edge Cases and Side Effects

- Objects with GCAT status `"N"` (non-operational, in orbit) that have also decayed are
  similarly affected — the fix script should cover all "in orbit" canonical statuses, not
  just `"O"`.
- The fix should only **override** status when SpaceTrack's decay class explicitly confirms
  a re-entry, not when the GP query simply returns empty (empty GP could mean the object's
  TLE data hasn't been updated yet, not necessarily that it decayed).
- `canonical.date_of_decay_or_change` and `sources.gcat.decay_date` should both be updated
  for consistency.
- The `promote_gcat_attributes.py` "fill-if-null" guard means re-running it won't revert the
  fix — but the fix script itself should use `UPDATE ... MERGE` (overwrite) semantics for the
  status and decay date fields.

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

### 3. No cross-source status reconciliation

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
| `database/transformations.py` | Canonical promotion logic — no decay inference |

---

## Proposed Fix

GCAT (Jonathan McDowell's General Catalog) is a **public dataset** updated regularly at
`https://www.planet4589.org/space/gcat/`. The local `gcat_satcat.tsv` is a stale snapshot.
Refreshing it is the correct authoritative fix — no SpaceTrack access needed.

### Step 1 — Refresh `gcat_satcat.tsv`

Download the latest file from GCAT and replace the local copy:
```
https://www.planet4589.org/space/gcat/data/derived/satcat.tsv
```
The updated GCAT record for S57687 should have its decay date and a decay status code (`R`,
`D`, etc.) by now.

### Step 2 — Re-run the GCAT bulk import

Re-running `import_gcat_bulk.py` updates `sources.gcat.status` and `sources.gcat.decay_date`
for existing records. **This alone will not fix the canonical status** because the bulk import's
update path only touches `sources.gcat`, not `canonical`.

### Step 3 — Fix the "fill-if-null" guard in `promote_gcat_attributes.py`

The current promotion query uses fill-if-null semantics for status:
```aql
status: doc.canonical.status != null ? doc.canonical.status : status_mapped
```
This means once `"in orbit"` is written, it is never overridden — even when the GCAT source
later records a decay.

**The fix**: status (and `date_of_decay_or_change`) should use **GCAT-wins-on-decay** semantics.
Specifically, when the GCAT source now maps to `"decayed"` (or another terminal state), it
should always overwrite the canonical value regardless of what was previously stored:

```aql
status: (status_mapped != null AND status_mapped != "in orbit")
    ? status_mapped
    : (doc.canonical.status != null ? doc.canonical.status : status_mapped)
```

This ensures decay/heliocentric/graveyard statuses always propagate from GCAT, while
non-terminal statuses (`"in orbit"`) still use fill-if-null to avoid overwriting richer data
from other sources.

Apply the same override logic to `date_of_decay_or_change`:
```aql
date_of_decay_or_change: g.decay_date != null
    ? g.decay_date
    : doc.canonical.date_of_decay_or_change
```

### Step 4 — Re-run `promote_gcat_attributes.py`

After steps 1–3, re-running the script will propagate the correct `"decayed"` status and
decay date to `canonical` for GCAT-S57687 and any other objects with the same staleness.

### Recommended approach

Implement steps 1–4. The regression test should verify that after refreshing GCAT data and
re-running promotion, `canonical.status` becomes `"decayed"` and
`canonical.date_of_decay_or_change` is non-null for NORAD 57687.

---

## Edge Cases and Side Effects

- The "GCAT-wins-on-decay" logic should only override with **terminal** GCAT statuses
  (`decayed`, `heliocentric`, `in disposal/graveyard orbit`) — not with `"in orbit"`, since
  `"in orbit"` from GCAT could be stale, and other approved sources may have more current data.
- Objects with GCAT status `"N"` that have also physically decayed (stale GCAT) are handled
  automatically once the GCAT file is refreshed and they show a decay code.
- `sources.gcat.decay_date` and `canonical.date_of_decay_or_change` should both be updated
  for consistency.
- The `promote_gcat_attributes.py` script currently filters for `sources_available == ["gcat"]`
  only. Objects with multiple sources (e.g., `["gcat", "celestrak"]`) are not touched by it.
  Those objects would need a separate reconciliation pass — but GCAT-S57687 is gcat-only, so
  this is not a blocker for the immediate fix.

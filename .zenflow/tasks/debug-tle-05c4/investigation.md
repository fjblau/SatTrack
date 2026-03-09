# TLE Bug Investigation: PRETTY Satellite (NORAD 58023)

## Bug Summary
The PRETTY satellite (international designator `2023-155H`, NORAD 58023) shows `"tle": {}` in its canonical document when viewed in the Detail Panel. TLE data is never populated for this satellite.

## Data Flow (How TLE Should Work)

1. User clicks PRETTY in Table View
2. `DetailPanel` fetches `/v2/satellite/2023-155H` → loads `fullDocument` from DB (currently shows `"tle": {}`)
3. Once `fullDocument.canonical.norad_cat_id` (58023) is available, `fetchCurrentTle()` fires
4. Calls `GET /v2/tle/58023` → backend calls `https://tle.ivanstanojevic.me/api/tle/58023`
5. **If data found**: frontend fires `POST /v2/tle/58023/persist` → `update_satellite_tle()` sets `canonical.tle = parsed_tle_data` in DB
6. **If not found**: frontend sets `_notFound: true` flag — **no persist call is made**

## Root Cause

**`tle.ivanstanojevic.me` does not have PRETTY (NORAD 58023)**

PRETTY is a small Austrian scientific cubesat launched October 2023. The `tle.ivanstanojevic.me` third-party API does not index this satellite. When the API returns no data, the backend `fetch_tle_by_norad_id()` returns `None`, the frontend skips the persist call, and `canonical.tle` stays `{}` in the database forever.

**File**: `api/services/tle_service.py`, function `_fetch_tle_by_norad_id_uncached()`

The function only queries one source (`tle.ivanstanojevic.me`) with no fallback.

## Secondary Issue: Field Name Mismatch in `update_canonical`

**File**: `database/transformations.py`, function `update_canonical()`

The `update_canonical` logic tries to recover TLE data from sources using field names `tle_line1` / `tle_line2`:

```python
tle_fields = ["tle_line1", "tle_line2"]
for field in tle_fields:
    canonical_field = "line1" if field == "tle_line1" else "line2"
    ...
    value = sources[source_name].get(field)  # looks for "tle_line1", "tle_line2"
```

But when `update_satellite_tle()` stores TLE data in `sources["tleapi"]`, it uses keys `line1` and `line2` (not `tle_line1`/`tle_line2`):

```python
doc["sources"]["tleapi"] = {
    "line1": tle_data.get("line1"),
    "line2": tle_data.get("line2"),
    ...
}
```

This mismatch means `update_canonical` will never recover TLE data from `tleapi` source through its standard promotion path. (The direct write `doc["canonical"]["tle"] = tle_data` in `update_satellite_tle` bypasses this and works correctly, but it means canonical.tle is never re-populated if it gets reset.)

## Affected Components

- `api/services/tle_service.py` — primary fix location
- `database/transformations.py` — secondary fix (field name mismatch)

## Proposed Solution

### Fix 1 (Primary): Add CelesTrak as fallback in `_fetch_tle_by_norad_id_uncached()`

When `tle.ivanstanojevic.me` returns no data (404 or null), fall back to CelesTrak's individual satellite TLE endpoint:

```
GET https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE
```

CelesTrak is the authoritative source for TLE data and has a much wider catalog. The response is plain-text TLE format (3 lines: name, line1, line2).

### Fix 2 (Secondary): Fix field name mismatch in `transformations.py`

In `update_canonical`, when looking for TLE data in `tleapi` source, also check `line1`/`line2` keys in addition to `tle_line1`/`tle_line2`. Alternatively, unify the field names: store the data under `tle_line1`/`tle_line2` in `tleapi` source (at write time in `update_satellite_tle`).

## Edge Cases / Side Effects

- CelesTrak may also not have data for very new or decayed satellites — the function should still return `None` gracefully in that case
- The CelesTrak fallback response needs TLE parsing (split 3 lines, validate line1 starts with "1 ")
- Caching applies to both sources via the existing cache infrastructure — no change needed
- The fix is backward-compatible: existing satellites with TLE data are unaffected

## Implementation Notes

- Fix 1 is essential and sufficient to resolve the PRETTY case
- Fix 2 is a correctness fix that prevents future data inconsistency but is not the root cause of the reported bug

# Investigation: TLE Data Not Found for International Designator '2022-156'

## Bug Summary

When fetching TLE data for international designator `2022-156` via the API endpoint
`GET /v2/tle/intldes/2022-156`, the response returns:

```json
{
  "data": null,
  "message": "TLE data not found for international designator '2022-156' on CelesTrak."
}
```

CelesTrak **does** have TLE data for objects from launch 2022-156 — three debris fragments
from the Artemis I / SLS mission are actively tracked. The failure is caused by a
broken data extraction step in the code.

---

## Root Cause Analysis

### Location
`api/services/tle_service.py` — functions `_fetch_tle_by_intl_des_uncached` and
`_fetch_tle_by_norad_id_uncached`, via helper `_celestrak_gp_to_tle_dict`.

### The Problem

The CelesTrak GP API (`https://celestrak.org/NORAD/elements/gp.php`) with `FORMAT=JSON`
returns orbital elements in GP format — fields like `MEAN_MOTION`, `ECCENTRICITY`, etc.
It does **not** include `TLE_LINE1` or `TLE_LINE2` in the JSON response (confirmed live).

`_celestrak_gp_to_tle_dict` extracts TLE data as:

```python
line1 = entry.get("TLE_LINE1")
line2 = entry.get("TLE_LINE2")
if not line1 or not line2:
    return None
```

Since neither key is present in the JSON response, the function always returns `None`.
As a result, `celestrak_found` stays `False`, the code falls through to the SpaceTrack
fallback, and if SpaceTrack credentials are not configured (or it also fails), `None`
is returned to the caller.

**CelesTrak returns valid data**, but the code silently discards it because it expects
fields that no longer exist in the JSON response format.

### Verification

```
GET https://celestrak.org/NORAD/elements/gp.php?INTDES=2022-156&FORMAT=JSON
→ 200 OK, returns 3 entries
→ Keys: OBJECT_NAME, OBJECT_ID, EPOCH, MEAN_MOTION, ECCENTRICITY, INCLINATION, ...
→ TLE_LINE1: absent
→ TLE_LINE2: absent
```

```
GET https://celestrak.org/NORAD/elements/gp.php?INTDES=2022-156&FORMAT=TLE
→ 200 OK, returns 3-line TLE text for all three pieces
```

---

## Debris Records That SHOULD Have TLE Data

Launch **2022-156** is the **Artemis I / SLS** mission (November 2022). Three debris
fragments are currently tracked by CelesTrak with active TLE data:

| OBJECT_ID | NORAD CAT ID | NAME    | Notes              |
|-----------|--------------|---------|--------------------|
| 2022-156D | 55904        | SLS DEB | Active — has TLE   |
| 2022-156E | 55905        | SLS DEB | Active — has TLE   |
| 2022-156G | 55907        | SLS DEB | Active — has TLE   |

Pieces A, B, C, F are not in the current CelesTrak GP catalog, likely because they
either left Earth orbit (Orion spacecraft, SLS upper stage) or re-entered the atmosphere.

---

## Affected Components

- `api/services/tle_service.py`:
  - `_celestrak_gp_to_tle_dict` — returns `None` for all CelesTrak GP JSON responses
  - `_fetch_tle_by_intl_des_uncached` — falls through to SpaceTrack because CelesTrak
    "finds" nothing (due to above)
  - `_fetch_tle_by_norad_id_uncached` — same issue for NORAD ID lookups

- `api/routers/tle.py`:
  - `GET /v2/tle/intldes/{intl_des}` — returns 200 with `data: null`
  - `GET /v2/tle/{norad_id}` — returns 200 with `data: null`
  - `POST /v2/tle/{norad_id}/persist` — would raise 404

---

## Proposed Solution

### Strategy: Switch to `FORMAT=TLE` for CelesTrak requests

Replace `FORMAT=JSON` with `FORMAT=TLE` (3-line text format). Parse the text response
to extract `name`, `line1`, `line2`, and derive `OBJECT_ID`/`NORAD_CAT_ID` from the
TLE lines themselves.

**TLE line 1 field layout** (fixed columns):
- Column 3–7 (0-indexed 2–6): NORAD catalog ID
- Column 9–16 (0-indexed 9–16): international designator (compact, no hyphen):
  `22156D` → year `22`, launch number `156`, piece `D` → standard form `2022-156D`

### Implementation Plan

1. **Add a TLE text parser** (`_parse_tle_text(text: str) -> list[dict]`):
   - Split into 3-line blocks (name / line1 / line2)
   - Extract `NORAD_CAT_ID` from line1[2:7].strip()
   - Extract compact intl designator from line1[9:17].strip()
   - Convert compact form to standard form: `22156D` → `2022-156D`
   - Return list of `{"name", "line1", "line2", "norad_cat_id", "intl_designator"}` dicts

2. **Update `_fetch_tle_by_norad_id_uncached`**:
   - Change `params["FORMAT"]` from `"JSON"` to `"TLE"`
   - Replace `response.json()` parsing with `_parse_tle_text(response.text)`
   - Keep the rest of the matching/fallback logic the same

3. **Update `_fetch_tle_by_intl_des_uncached`**:
   - Same format change and parsing update
   - Keep OBJECT_ID normalization + exact-match logic using the parsed `intl_designator`

4. **Remove `_celestrak_gp_to_tle_dict`** (no longer needed) or keep as dead code with
   a deprecation comment.

### Edge Cases to Consider

- **Empty TLE response**: CelesTrak returns an HTTP 200 with an empty body when no
  object is found. The parser should return an empty list in this case.
- **Compact year rollover**: Years 57–99 map to 1957–1999; years 00–56 map to 2000–2056.
  The conversion from `YY` to `YYYY` must handle both.
- **Piece letters vs. no piece**: Some entries may have no piece letter (launch vehicle
  only). The parser should handle designators of varying length gracefully.
- **SpaceTrack fallback**: The SpaceTrack service already uses `FORMAT=JSON` via its own
  endpoint and its `_gp_entry_to_tle_dict` has the same bug — but SpaceTrack's JSON
  does include `TLE_LINE1` / `TLE_LINE2` fields (confirmed by existing code comments and
  service design). SpaceTrack's service is unaffected.

### Alternative: Two-step fetch (JSON → TLE by NORAD ID)
- Use `FORMAT=JSON` to identify the best matching `NORAD_CAT_ID`
- Then fetch `FORMAT=TLE` with `CATNR={norad_id}` to get the TLE lines
- More HTTP requests but simpler parsing
- Rejected in favor of single-request solution above

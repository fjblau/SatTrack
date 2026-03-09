# TLE Bug Investigation: PRETTY Satellite (NORAD 58023)

## Bug Summary
The PRETTY satellite (international designator `2023-155H`, NORAD 58023) shows `"tle": {}` in the "Show Data Record" modal, even though TLE data IS displayed correctly in the Two-Line Element section of the Detail Panel.

## Data Flow

1. User clicks PRETTY → `DetailPanel` receives `object`
2. `fetchSatelliteData()` runs → fetches `/v2/satellite/2023-155H` from DB → sets `fullDocument` (with `canonical.tle: {}`)
3. Once `fullDocument.canonical.norad_cat_id = 58023` is available, `fetchCurrentTle()` fires
4. Fetches `/v2/tle/58023` → `tle.ivanstanojevic.me` returns valid TLE → `currentTle` state is set → TLE displays in UI ✓
5. Persist fires **fire-and-forget**: `POST /v2/tle/58023/persist` → backend calls `update_satellite_tle()` → writes `canonical.tle = parsed_tle_data` to DB
6. **`fullDocument` state is NEVER updated after persist**
7. User clicks "Show Data Record" → `DataRecordModal` renders `fullDocument` → shows stale `tle: {}` from step 2

## Root Cause

**`fullDocument` is never refreshed after the TLE persist call completes.**

In `react-app/src/components/DetailPanel.jsx` (lines 141–149), the persist call is fire-and-forget with only a `.catch()` handler:

```javascript
fetch(
  `${API_ENDPOINTS.TLE}/${encodeURIComponent(fullDocument.canonical.norad_cat_id)}/persist`,
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier }),
  }
).catch(err => console.error('TLE persist error:', err))
```

The persist endpoint returns `{ "tle": parsed_tle_data, "timestamp": ... }` but the response is **completely ignored**. `fullDocument` retains the pre-persist snapshot, so the Data Record modal always shows `"tle": {}` for any satellite opened for the first time in a session.

## Secondary Issue: Field Name Mismatch in `update_canonical`

In `database/transformations.py`, `update_canonical()` looks for `tle_line1` / `tle_line2` in sources:

```python
tle_fields = ["tle_line1", "tle_line2"]
for field in tle_fields:
    ...
    value = sources[source_name].get(field)  # looks for "tle_line1", "tle_line2"
```

But `update_satellite_tle()` stores TLE in `sources["tleapi"]` as `line1` / `line2`:

```python
doc["sources"]["tleapi"] = {
    "line1": tle_data.get("line1"),
    "line2": tle_data.get("line2"),
    ...
}
```

This mismatch means `update_canonical` can never recover TLE from the `tleapi` source through the standard promotion path. (The direct write `doc["canonical"]["tle"] = tle_data` in `update_satellite_tle` works correctly, but if `canonical.tle` is ever reset by an `update_canonical` call, it won't be re-populated.)

## Affected Components

- **`react-app/src/components/DetailPanel.jsx`** — primary fix location (lines 141–149)
- **`database/transformations.py`** — secondary fix (field name mismatch)

## Proposed Fix

### Fix 1 (Primary): Update `fullDocument` after persist succeeds — `DetailPanel.jsx`

Replace the fire-and-forget persist call with one that handles the response and updates `fullDocument`:

```javascript
fetch(
  `${API_ENDPOINTS.TLE}/${encodeURIComponent(fullDocument.canonical.norad_cat_id)}/persist`,
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier }),
  }
)
.then(async (res) => {
  if (res.ok) {
    const data = await res.json()
    setFullDocument(prev => ({
      ...prev,
      canonical: {
        ...prev.canonical,
        tle: data.tle
      }
    }))
  }
})
.catch(err => console.error('TLE persist error:', err))
```

The persist endpoint already returns `{ "tle": parsed_tle_data, "timestamp": ... }` — no backend changes needed.

### Fix 2 (Secondary): Fix field name mismatch — `database/transformations.py`

In `update_canonical`, when checking `tleapi` source, also check `line1`/`line2` keys. The cleanest fix is to update the field lookup to handle both naming conventions:

```python
tle_field_aliases = {
    "tle_line1": ["tle_line1", "line1"],
    "tle_line2": ["tle_line2", "line2"],
}
for field, aliases in tle_field_aliases.items():
    canonical_field = "line1" if "line1" in field else "line2"
    if canonical["tle"].get(canonical_field):
        continue
    for source_name in source_priority:
        if source_name in sources:
            for alias in aliases:
                value = sources[source_name].get(alias)
                if value is not None:
                    canonical["tle"][canonical_field] = value
                    break
            if canonical["tle"].get(canonical_field):
                break
```

## Edge Cases / Side Effects

- Fix 1 is minimal and safe — only updates the in-memory `fullDocument` state, no extra network calls
- If persist fails (400/404/500), `fullDocument` is not updated — consistent with current behavior
- Fix 2 is a defensive correctness fix — prevents TLE data loss if `update_canonical` is called after `update_satellite_tle`

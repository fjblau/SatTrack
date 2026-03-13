# Investigation: TLE Data for Debris Objects via SpaceTrack

## Bug Summary

When a DEBRIS object is opened from the main table, TLE data is almost never displayed. The current system only fetches TLE data from `tle.ivanstanojevic.me`, which covers primarily active/notable satellites and returns 404 for most debris objects. Additionally, the TLE section in the UI is entirely hidden if `canonical.norad_cat_id` is absent from the database record — which is common for debris objects.

SpaceTrack (https://www.space-track.org) is the authoritative US Space Command catalog that tracks **all** catalogued objects including debris, rocket bodies, and fragments. The project already references SpaceTrack in architecture docs and import scripts.

---

## Root Cause Analysis

### Two blocking conditions prevent TLE data from appearing for debris:

**1. UI gating on `norad_cat_id`** — `DetailPanel.jsx` line 364:
```jsx
{fullDocument?.canonical?.norad_cat_id && (
  <div className="detail-section">
    <h3>Two-Line Element (TLE)</h3>
    ...
  </div>
)}
```
The entire TLE section is hidden unless `norad_cat_id` is populated in the database record. Debris objects frequently lack this field.

**2. TLE API doesn't cover debris** — `tle_service.py` `_fetch_tle_by_norad_id_uncached()`:
```python
url = f"https://tle.ivanstanojevic.me/api/tle/{norad_id}"
```
This third-party API covers common/active satellites only. Even if a NORAD ID is present, it returns 404 for most debris.

**3. No SpaceTrack integration in the backend** — Despite being referenced in docs and architecture, no actual SpaceTrack API calls exist in `api/services/` or `api/routers/`.

### Data flow for a clicked debris row:
1. `App.jsx`: Row click → `selectedObject` set (includes `_norad_id` from canonical)
2. `DetailPanel.jsx` useEffect: Fetches `/v2/satellite/{identifier}` → gets `fullDocument`
3. Checks `fullDocument?.canonical?.norad_cat_id` → **often undefined for debris → stops here**
4. If norad_id exists: Fetches `/v2/tle/{norad_id}` → `tle.ivanstanojevic.me` → **404 for debris**

---

## Affected Components

- **Frontend**: `react-app/src/components/DetailPanel.jsx` (lines 125–178, 364–389)
- **Backend service**: `api/services/tle_service.py` — no SpaceTrack fallback
- **Backend router**: `api/routers/tle.py` — uses only the existing TLE service
- **Config**: `config.py` — has `ExternalServicesConfig` but SpaceTrack credentials not defined
- **Env**: `.env.example` — no SpaceTrack credentials documented

---

## Proposed Solution

### Overview
Add SpaceTrack as a fallback TLE data source when the primary source fails, specifically triggered for DEBRIS-type objects.

### Backend Changes

#### 1. Add SpaceTrack credentials to config and environment
In `config.py`, add to `ExternalServicesConfig`:
```python
SPACETRACK_BASE_URL: str = "https://www.space-track.org"
SPACETRACK_USERNAME: str = os.getenv("SPACETRACK_USERNAME", "")
SPACETRACK_PASSWORD: str = os.getenv("SPACETRACK_PASSWORD", "")
```

Add to `.env.example`:
```
SPACETRACK_USERNAME=your_email@example.com
SPACETRACK_PASSWORD=your_password
```

#### 2. Create `api/services/spacetrack_service.py`
- Authenticate with SpaceTrack via session-based login (`/ajaxauth/login`)
- Fetch TLE by NORAD ID: `GET /basicspacedata/query/class/gp/NORAD_CAT_ID/{norad_id}/format/json`
- Optionally fetch by international designator: `GET /basicspacedata/query/class/gp/INTLDES/{intl_des}/format/json`
- Return TLE in the same `{name, line1, line2, source, date}` format as the existing service
- Cache session token (reuse within TTL to avoid repeated logins)
- Return `None` if credentials not configured (graceful degradation)

#### 3. Modify `api/services/tle_service.py`
Extend `_fetch_tle_by_norad_id_uncached()` to fall back to SpaceTrack when the primary API returns None:
```python
def _fetch_tle_by_norad_id_uncached(norad_id: str) -> Optional[Dict]:
    # Try primary source
    result = _fetch_from_tle_api(norad_id)
    if result:
        return result
    # Fallback: SpaceTrack
    return fetch_tle_from_spacetrack(norad_id)
```

#### 4. Add new endpoint to `api/routers/tle.py` (optional enhancement)
A new `GET /v2/tle/intldes/{intl_des}` endpoint for fetching TLE by international designator directly from SpaceTrack. This handles debris with international designator but no NORAD ID in the database.

### Frontend Changes

#### 5. Modify `react-app/src/components/DetailPanel.jsx`

**Change 1**: Don't gate the TLE section on `norad_cat_id` alone. Also show it for DEBRIS objects using the international designator or the `_norad_id` already available on the `object` prop.

**Change 2**: For DEBRIS objects without `canonical.norad_cat_id`, attempt TLE fetch using:
- The `_norad_id` already available in `object` prop (set from `canonical.norad_cat_id` in `App.jsx` line 153)  
- The international designator as fallback query

Updated logic (sketch):
```jsx
const isDebris = object?.['Object Type']?.toLowerCase().includes('debris')
const noradId = fullDocument?.canonical?.norad_cat_id || object?._norad_id

useEffect(() => {
  if (!object || (!noradId && !isDebris)) {
    setCurrentTle(null)
    return
  }
  // fetch TLE with noradId, or for debris fallback to intl designator query
  ...
}, [noradId, object?.['International Designator']])
```

**Change 3**: Show TLE section when object is DEBRIS even without norad_cat_id, displaying a loading state and then the result (or "not available" message):
```jsx
{(fullDocument?.canonical?.norad_cat_id || isDebris) && (
  <div className="detail-section">
    <h3>Two-Line Element (TLE)</h3>
    ...
  </div>
)}
```

---

## Edge Cases & Considerations

- **No credentials**: If `SPACETRACK_USERNAME`/`SPACETRACK_PASSWORD` not set, skip SpaceTrack gracefully and show "TLE data not available" (no crash)
- **Rate limiting**: SpaceTrack has rate limits; existing cache layer (1h TTL) already in `tle_service.py` provides protection
- **Session expiry**: SpaceTrack sessions expire; service should re-authenticate on 401 response
- **NORAD ID gaps**: Some debris objects have no NORAD ID anywhere. Querying by international designator via SpaceTrack can resolve this — SpaceTrack returns the NORAD ID alongside TLE data which can optionally be persisted back to the database
- **Object type values**: Need to verify exact string values used in `canonical.object_type` for debris (e.g., "Debris", "DEBRIS", "rocket body") — the filter `object_type` already uses `LIKE` with `%pattern%` so case is inconsistent

---

## Implementation Priority Order

1. `config.py` — add SpaceTrack credentials config
2. `.env.example` — document new env vars
3. `api/services/spacetrack_service.py` — new SpaceTrack client
4. `api/services/tle_service.py` — add SpaceTrack fallback
5. `react-app/src/components/DetailPanel.jsx` — show TLE for DEBRIS, use norad_id from object prop
6. `api/routers/tle.py` — optionally add intl designator endpoint
7. `tests/unit/test_tle_service.py` — add tests for SpaceTrack fallback

---

## Implementation Notes

### What was already implemented (pre-existing in codebase)
At time of implementation, items 5–6 were already in place:
- `DetailPanel.jsx` already had `DEBRIS_OBJECT_TYPES`, `isDebrisObject()`, and the full debris TLE fetch flow (including intl designator fallback and auto-persistence).
- `tle_service.py` already used CelesTrak GP API (not `tle.ivanstanojevic.me`) via `_fetch_tle_by_intl_des_uncached`.
- `api/routers/tle.py` already had `GET /v2/tle/intldes/{intl_des:path}`.
- `react-app/src/config/constants.js` already had `TLE_INTLDES`.

### Changes made during implementation
1. **`config.py`** — Added `SPACETRACK_BASE_URL`, `SPACETRACK_USERNAME`, `SPACETRACK_PASSWORD` to `ExternalServicesConfig`.
2. **`.env.example`** — Documented SpaceTrack credential env vars.
3. **`api/services/spacetrack_service.py`** (new) — Session-based SpaceTrack client with `fetch_tle_from_spacetrack_by_norad_id()` and `fetch_tle_from_spacetrack_by_intl_des()`. Gracefully skips when credentials are absent. Reuses session within a 2-hour TTL. Re-authenticates on 401.
4. **`api/services/tle_service.py`** — Refactored `_fetch_tle_by_norad_id_uncached()` and `_fetch_tle_by_intl_des_uncached()` to break out of the CelesTrak retry loop (instead of returning `None`) when no data is found, then fall through to SpaceTrack.
5. **`tests/unit/test_spacetrack_service.py`** (new) — 12 unit tests covering GP entry conversion, no-credentials graceful degradation, session failure, successful fetch, exact-match selection, and tle_service fallback integration.

### Test results
```
22 passed in 0.15s
```

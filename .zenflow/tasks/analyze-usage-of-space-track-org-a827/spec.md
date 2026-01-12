# Technical Specification: Space-Track.org API Usage Analysis

## Task Difficulty
**Easy** - Straightforward codebase analysis, no implementation required.

## Executive Summary
The Space-Track.org API is **actively being used** in the Kessler codebase in two distinct contexts:
1. **Data import script** for bulk TLE (Two-Line Element) data ingestion
2. **Runtime API endpoint** for on-demand TLE lookups by NORAD ID

## Technical Context

### Language & Dependencies
- **Language**: Python 3.11
- **Framework**: FastAPI (backend)
- **HTTP Library**: `requests`
- **Authentication**: Session-based (credentials required)
- **Environment Variables**: `SPACE_TRACK_USER`, `SPACE_TRACK_PASS`

### Space-Track.org API Details
- **Authentication Endpoint**: `https://www.space-track.org/ajaxauth/login`
- **Data Endpoint**: `https://www.space-track.org/basicspacedata/query/class/gp/NORAD_CAT_ID/{norad_id}/orderby/TLE_LINE1%20ASC/format/tle`
- **Authentication Method**: Session cookies via POST to login endpoint
- **Data Format**: TLE (Two-Line Element) text format

## Current Usage

### 1. Import Script: `import_spacetrack_tle.py`

**Purpose**: Bulk import TLE data from Space-Track for all satellites with NORAD IDs

**Key Functions**:
- `get_space_track_session()` (lines 22-45): Creates authenticated session
- `fetch_tle_from_space_track()` (lines 48-69): Fetches TLE by NORAD ID
- `import_space_track_tle()` (lines 96-146): Main import function with parallel execution

**Behavior**:
- Queries MongoDB for all satellites with `canonical.norad_cat_id`
- Fetches TLE data from Space-Track for each satellite (10 concurrent workers)
- Stores TLE data in MongoDB under `sources.spacetrack`
- Updates canonical TLE data via `update_canonical()` function
- Requires `SPACE_TRACK_USER` and `SPACE_TRACK_PASS` environment variables

**Usage Pattern**: Manual/scheduled data import (offline batch process)

### 2. Runtime API Endpoint: `api.py`

**Endpoint**: `GET /v2/tle/{norad_id}` (line 618)

**Function**: `fetch_tle_by_norad_id()` (lines 579-615)

**Behavior**:
- Checks for `SPACE_TRACK_USER` and `SPACE_TRACK_PASS` environment variables
- If credentials available:
  - Authenticates with Space-Track
  - Fetches fresh TLE data for the requested NORAD ID
  - Returns TLE with `source: "space-track"`
- If credentials unavailable or fetch fails:
  - Returns `None` (endpoint falls back to error message)
  
**Client Usage**:
- Frontend component `DetailPanel.jsx` (lines 124-148) calls this endpoint
- Displays current TLE data in satellite detail view
- Gracefully handles failures with error message

**Error Message**: "TLE data not found for NORAD ID {norad_id}. Recent satellites may require Space-Track API authentication." (line 632)

### 3. Data Architecture Integration: `db.py`

**Source Priority**: Line 194
```python
"source_priority": ["unoosa", "celestrak", "spacetrack", "kaggle"]
```

**Canonical Update Logic** (lines 204-257):
- Space-Track data stored under `sources.spacetrack`
- Space-Track is third priority for canonical TLE data (after UNOOSA and CelesTrak)
- TLE fields: `tle_line1`, `tle_line2`

## Configuration Status

### Environment Variables
**Required for Space-Track API**:
- `SPACE_TRACK_USER` - Space-Track account username
- `SPACE_TRACK_PASS` - Space-Track account password

**Configuration File**: `.env.example`
- Does **NOT** include Space-Track credentials
- Only includes `MONGO_URI` and `CORS_ORIGINS`
- Suggests Space-Track integration is **optional/not configured by default**

### Graceful Degradation
Both Space-Track integrations handle missing credentials gracefully:
- Import script: Prints error and skips Space-Track import
- API endpoint: Returns `None`, allowing fallback behavior
- No system crashes or hard dependencies

## API Usage Summary

| Location | Type | Credentials Required | Impact if Missing |
|----------|------|---------------------|-------------------|
| `import_spacetrack_tle.py` | Data import script | Yes | No Space-Track TLE data imported |
| `api.py:579-633` | Runtime endpoint `/v2/tle/{norad_id}` | Yes | TLE endpoint returns error message |
| `DetailPanel.jsx` | Frontend component | Indirect | No current TLE display |

## Dependencies

**Files that reference Space-Track**:
- `import_spacetrack_tle.py` - Primary import script
- `api.py` - Runtime API endpoint
- `db.py` - Data model (source priority, storage schema)
- `check_tle_status.py` - Utility script (checks for Space-Track TLE data)
- Various documentation files (mentioned in context)

## Conclusion

**Yes, the Space-Track.org API is still actively used** in the Kessler codebase:

1. **Primary Use Case**: Bulk TLE data import via `import_spacetrack_tle.py`
2. **Secondary Use Case**: On-demand TLE lookups via `/v2/tle/{norad_id}` endpoint
3. **Configuration**: Optional - credentials not in `.env.example`
4. **Integration Quality**: Well-designed with graceful degradation
5. **Data Flow**: Space-Track → MongoDB (`sources.spacetrack`) → Canonical TLE (third priority)

### Recommendations
- Space-Track integration is **production-ready** but **optional**
- Credentials should be added to `.env.example` as commented-out optional configuration
- Frontend could benefit from better UX when Space-Track credentials are unavailable
- Consider documenting Space-Track account creation process for users

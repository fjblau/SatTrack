# Data Source Analysis and Multi-Source Import Strategy

**Analysis Date**: February 17, 2026  
**Current Database**: 17,791 satellites in ArangoDB

---

## Executive Summary

Four complementary data sources are available for importing recent satellite launches (Sept 2025 - Feb 2026):

1. **GCAT** (General Catalog): 1,845 recent launches with technical specifications
2. **Kaggle**: 14,623 satellites with orbital analytics (updated Feb 16, 2026)
3. **SatNOGS**: Real-time operational status via API (partial coverage)
4. **UNOOSA**: Official UN registration data (delayed but authoritative)

**Primary Key**: NORAD Catalog ID for matching across all sources

---

## Data Source Details

### 1. GCAT (General Catalog)

**Status**: ✅ Downloaded and ready  
**File**: `gcat_satcat.tsv` (18.2 MB)  
**Last Updated**: January 11, 2026  
**Total Records**: 67,404 satellites  
**Recent Launches**: 1,845 (Sept-Dec 2025)  
**Max NORAD ID**: 67362

**Format**: Tab-separated (42 columns)

**Key Fields**:
- Column 2: `Satcat` (NORAD ID) - **Primary matching key**
- Column 3: `Launch_Tag` (International designator)
- Column 6: `Name` (Satellite name)
- Column 8: `LDate` (Launch date, format: "YYYY MMM DD")
- Column 16: `State` (Country code)
- Column 17: `Manufacturer`
- Column 20: `Mass` (kg)
- Column 26-30: Physical dimensions (length, diameter, span)
- Column 34-38: Orbital parameters (perigee, apogee, inclination)
- Column 40: `OpOrbit` (Operational orbit designation)

**Sample Recent Launch** (Dec 7, 2025):
```
NORAD 66925: Starlink 35945
NORAD 66926: Starlink 35942
...
```

**Strengths**:
- Most comprehensive technical specifications
- Recent launch data through Jan 11, 2026
- Authoritative source for physical satellite properties
- Includes manufacturer and mission details

**Limitations**:
- Update frequency ~monthly
- Some NORAD IDs marked "NNA" (not yet assigned)
- Missing some fields for classified satellites

---

### 2. Kaggle Satellite Catalog

**Status**: ✅ Downloaded and ready  
**File**: `/Users/frankblau/Downloads/current_catalog.csv` (2.7 MB)  
**Last Updated**: February 16, 2026 (yesterday!)  
**Total Records**: 14,623 satellites  
**Max NORAD ID**: 67796 (Crew Dragon 12)  
**Import Script**: `scripts/import/import_kaggle_catalog.py` ✅ Already exists!

**Format**: CSV with 19 columns

**Key Fields**:
- `norad_id` - **Primary matching key**
- `name`
- `object_type` (PAYLOAD, ROCKET BODY, DEBRIS)
- `country`
- `satellite_constellation`
- `altitude_km`
- `altitude_category` (Very Low LEO, Low LEO, Mid LEO, High LEO)
- `orbital_band` (LEO-Polar, LEO-Inclined, MEO, GEO, etc.)
- `congestion_risk` (HIGH, MEDIUM, LOW)
- `inclination`, `eccentricity`
- `orbit_lifetime_category` (<1yr, 1-5yr, 5-10yr, 10+yr)
- `mean_motion`, `epoch`
- `data_source` (celestrak)
- `snapshot_date`, `last_seen`

**Sample Record**:
```csv
67796,CREW DRAGON 12,PAYLOAD,Other,420.69,Very Low LEO,LEO-Inclined,HIGH,51.6319,0.00110201,2024,0,<1yr,15.48645386,2026-02-16 12:54:05.724000,celestrak,2026-02-16,US,2026-02-16
```

**Strengths**:
- **Most recent data** (updated daily from CelesTrak)
- Unique orbital analytics (congestion risk, lifetime estimates)
- Pre-categorized altitude and orbital bands
- Clean, structured CSV format
- **Import script already exists and tested**

**Limitations**:
- Limited to operational satellites tracked by CelesTrak
- No physical specifications (mass, dimensions)
- No manufacturer or mission details

**Value-Add**:
- `congestion_risk`: Collision probability assessment
- `orbital_band`: Standardized orbit classification
- `orbit_lifetime_category`: Debris lifetime prediction
- `altitude_category`: Quick altitude classification

---

### 3. SatNOGS Database API

**Status**: ✅ API accessible and tested  
**Endpoint**: `https://db.satnogs.org/api/satellites/`  
**Query Method**: `?norad_cat_id={id}`  
**Format**: JSON

**Test Results**:
- ✅ NORAD 25544 (ISS): Full data returned
- ✅ NORAD 48274 (CSS Tianhe): Full data returned
- ❌ NORAD 67796 (recent): Empty array (not yet in database)

**Key Fields**:
- `sat_id` (SatNOGS internal ID)
- `norad_cat_id` - **Primary matching key**
- `name`, `names` (alternative names)
- `status` (alive, dead, re-entered)
- `decayed` (decay date)
- `launched`, `deployed` (dates)
- `website`, `operator`
- `countries`
- `telemetries` (transmitter decoders)
- `updated` (last observation)
- `is_frequency_violator`

**Sample Response**:
```json
{
  "sat_id": "XSKZ-5603-1870-9019-3066",
  "norad_cat_id": 25544,
  "name": "ISS",
  "names": "ZARYA, RS0ISS, NA1SS",
  "status": "alive",
  "launched": "1998-11-20T00:00:00Z",
  "website": "https://www.nasa.gov/mission_pages/station/main/index.html",
  "countries": "RU,US",
  "telemetries": [{"decoder": "iss"}],
  "updated": "2025-08-01T05:17:04.759872Z"
}
```

**Strengths**:
- Real-time operational status from ground observations
- Transmitter frequencies and modes
- Community-verified data
- Identifies frequency violators
- Decay/re-entry tracking

**Limitations**:
- **Not all satellites are tracked** (focus on amateur radio & active)
- Recent launches may take weeks to appear
- Rate limiting on API (community resource)
- Missing many classified/non-transmitting satellites

**Coverage Estimate**: ~30-40% of total satellite population (bias toward operational, transmitting satellites)

---

### 4. Current Database (ArangoDB)

**Status**: ✅ Connected  
**Total Records**: 17,791 satellites  
**Database**: `kessler.satellites` (ArangoDB)

**Document Structure** (Envelope Pattern):
```javascript
{
  "_key": "auto-generated",
  "identifier": "2025-206B",  // International designator or NORAD-{id}
  "canonical": {
    "name": "...",
    "norad_cat_id": 12345,
    "date_of_launch": "...",
    "country": "...",
    // ... promoted from sources based on priority
  },
  "sources": {
    "unoosa": { /* UNOOSA-specific fields */ },
    "celestrak": { /* CelesTrak-specific fields */ },
    "kaggle": { /* Kaggle-specific fields */ },
    "gcat": { /* GCAT-specific fields (to be added) */ },
    "satnogs": { /* SatNOGS-specific fields (to be added) */ }
  },
  "metadata": {
    "created_at": "...",
    "last_updated_at": "...",
    "sources_available": ["unoosa", "celestrak", "kaggle"],
    "source_priority": ["unoosa", "celestrak", "tleapi", "kaggle"],
    "transformations": [...]
  }
}
```

**Source Priority** (for canonical field promotion):
1. **UNOOSA** - Official UN registration (most authoritative for legal/registration data)
2. **CelesTrak** - Reliable TLE data
3. **TLE API** - Fallback TLE source
4. **Kaggle** - Analytics and categorization

**Proposed Update** (after GCAT + SatNOGS import):
1. **UNOOSA** - Official registration
2. **GCAT** - Technical specifications (mass, dimensions, manufacturer)
3. **CelesTrak** - TLE data
4. **SatNOGS** - Operational status (for live satellites only)
5. **Kaggle** - Analytics and risk assessment

---

## Matching Strategy

### Primary Key: NORAD Catalog ID

All sources use NORAD ID as the universal identifier:
- **GCAT**: Column 2 (`Satcat`)
- **Kaggle**: `norad_id` field
- **SatNOGS**: `norad_cat_id` field
- **Database**: `canonical.norad_cat_id`

### Matching Algorithm

```python
def find_existing_satellite(norad_id):
    """Match by NORAD ID across all sources"""
    return collection.find_one({
        "$or": [
            {"canonical.norad_cat_id": norad_id},
            {"sources.gcat.norad_cat_id": norad_id},
            {"sources.kaggle.norad_cat_id": norad_id},
            {"sources.celestrak.norad_id": norad_id},
            {"sources.satnogs.norad_cat_id": norad_id}
        ]
    })
```

### Fallback Matching (for NORAD IDs not yet assigned)

1. **International Designator** (e.g., "2025-206B")
   - GCAT: Column 3 (`Launch_Tag`)
   - Database: `canonical.international_designator`

2. **Name + Launch Date** (last resort)
   - Fuzzy matching on satellite name
   - Verify launch date proximity

### Handling Edge Cases

**NORAD "NNA" (Not yet assigned)**:
- These appear in GCAT for very recent launches
- Import with temporary identifier: `GCAT-{JCAT_ID}`
- Update when NORAD ID is assigned

**Duplicate Detection**:
- Check for existing NORAD ID before creating new record
- Prefer updating existing record with new source data
- Log conflicts for manual review

**Missing NORAD IDs**:
- Some satellites never receive NORAD IDs (classified missions)
- Use international designator as primary identifier
- Store in `identifier` field

---

## Import Order and Strategy

### Phase 1: GCAT Import (1,845 recent launches)

**Objective**: Import Sept-Dec 2025 launches with technical specifications

**Process**:
1. Parse GCAT TSV (filter for `LDate >= 2025-09-01`)
2. Extract NORAD ID, name, launch date, country, orbital params
3. Match existing satellites by NORAD ID
4. **If match found**: Add `sources.gcat` with technical data
5. **If no match**: Create new satellite with identifier `NORAD-{id}` or `{intl_designator}`
6. Update canonical fields based on new source priority

**Expected Impact**:
- ~1,845 new/updated records
- Database grows to ~19,600 satellites
- Rich technical specs added (mass, manufacturer, dimensions)

**Import Script**: `scripts/import/import_gcat_launches.py` (to be created)

---

### Phase 2: Kaggle Import (14,623 satellites with analytics)

**Objective**: Enrich all satellites with orbital analytics

**Process**:
1. Run existing script: `scripts/import/import_kaggle_catalog.py`
2. Match by NORAD ID
3. Add `sources.kaggle` with analytics:
   - Congestion risk assessment
   - Orbital band classification
   - Lifetime category
   - Altitude categorization

**Expected Impact**:
- ~14,623 satellites enriched
- All operational satellites get risk/analytics data
- May add some satellites not in GCAT (historical or other sources)

**Import Script**: ✅ Already exists! Just run with correct CSV path

**Command**:
```bash
python3 scripts/import/import_kaggle_catalog.py /Users/frankblau/Downloads/current_catalog.csv
```

---

### Phase 3: SatNOGS Import (Operational status)

**Objective**: Add real-time operational status for tracked satellites

**Process**:
1. Query all satellites with NORAD IDs from database
2. For each NORAD ID, query SatNOGS API: `https://db.satnogs.org/api/satellites/?norad_cat_id={id}`
3. If data returned, add `sources.satnogs` with:
   - Operational status (alive/dead/re-entered)
   - Transmitter data
   - Last observation date
   - Operator and website
4. Update `canonical.status` if SatNOGS data is more recent
5. Rate limit: 1 request per second (polite to community API)

**Expected Impact**:
- ~5,000-7,000 satellites enriched (estimated coverage)
- Know which satellites are actually transmitting
- Ground-truth operational status

**Import Script**: `scripts/import/import_satnogs_status.py` (to be created)

**Estimated Runtime**: 
- 17,791 satellites × 1s per request = ~5 hours
- Optimization: Batch query or filter to active satellites only

---

### Phase 4 (Optional): UNOOSA Refresh

**Objective**: Add official UN registration for recently launched satellites

**Process**:
1. Check UNOOSA registry for new entries (Sept 2025 onwards)
2. Export any new registration data
3. Merge with existing records by NORAD ID or international designator
4. Update `sources.unoosa` with official registration details

**Timeline**: Can be deferred (registration typically lags launch by months)

---

## Data Quality and Validation

### Verification Checks

**After Each Import Phase**:
1. **Record Count**: Verify expected number of new/updated records
2. **NORAD ID Range**: Check max NORAD ID matches source
3. **Source Attribution**: Confirm `sources.{source}` exists for imported records
4. **Canonical Promotion**: Verify fields promoted correctly
5. **No Duplicates**: Check for duplicate NORAD IDs
6. **Data Integrity**: Sample check field values

### Multi-Source Coverage Metrics

**After All Imports**:
- Records with 1 source: X
- Records with 2 sources: X
- Records with 3+ sources: X
- Records with GCAT: ~67,000+
- Records with Kaggle: ~14,600
- Records with SatNOGS: ~5,000-7,000
- Records with UNOOSA: ~17,800 (existing)

**Quality Indicators**:
- Higher source count = more complete data
- GCAT + Kaggle = best technical + analytical coverage
- UNOOSA + GCAT = authoritative official + technical data
- SatNOGS = ground-truth operational status

---

## Value-Add by Source

### GCAT Contributions
- **Technical specifications**: Mass, dimensions, manufacturer
- **Mission details**: Function, bus type, motor
- **Recent launches**: Most current launch data
- **Orbital design**: Operational orbit classification

### Kaggle Contributions
- **Risk assessment**: Congestion risk for collision avoidance
- **Orbit classification**: Standardized altitude/band categories
- **Lifetime prediction**: Debris persistence estimates
- **Analytics**: Mean motion, eccentricity analysis

### SatNOGS Contributions
- **Live status**: Ground-observed operational state
- **Transmitter data**: Frequencies, modes, protocols
- **Community intelligence**: Amateur radio observations
- **Decay tracking**: Confirmed re-entries

### UNOOSA Contributions
- **Legal authority**: Official UN registration
- **Registration documents**: Treaty compliance
- **Launch vehicle**: Official launch manifest
- **Function**: Authorized mission purpose

---

## Implementation Timeline

| Phase | Task | Estimated Time | Dependencies |
|-------|------|----------------|--------------|
| 1 | Create GCAT import script | 2-3 hours | GCAT TSV analysis |
| 1 | Run GCAT import | 5-10 minutes | Import script ready |
| 1 | Verify GCAT import | 15 minutes | Import complete |
| 2 | Run Kaggle import | 5-10 minutes | Existing script |
| 2 | Verify Kaggle import | 15 minutes | Import complete |
| 3 | Create SatNOGS import script | 2-3 hours | API testing |
| 3 | Run SatNOGS import | 4-6 hours | Rate limiting |
| 3 | Verify SatNOGS import | 15 minutes | Import complete |
| 4 | UNOOSA refresh (optional) | TBD | Registry check |

**Total Estimated Time**: 8-12 hours (excluding SatNOGS API wait time)

---

## Risks and Mitigations

### Risk 1: API Rate Limiting (SatNOGS)
- **Impact**: Import could be blocked or delayed
- **Mitigation**: 1-second delays between requests, respect community API
- **Alternative**: Filter to only active satellites first

### Risk 2: NORAD ID Conflicts
- **Impact**: Duplicate records or data corruption
- **Mitigation**: Strict NORAD ID deduplication, log all conflicts

### Risk 3: Data Staleness
- **Impact**: GCAT updated monthly, may miss very recent launches
- **Mitigation**: Kaggle provides daily updates as backup source

### Risk 4: Incomplete Coverage
- **Impact**: Not all satellites in all sources
- **Mitigation**: Multi-source strategy ensures redundancy

---

## Success Criteria

✅ **Phase 1 Success**:
- 1,845+ satellites from Sept-Dec 2025 imported
- All have `sources.gcat` data
- Launch dates verified (earliest: 2025-09-01)

✅ **Phase 2 Success**:
- 14,623 satellites from Kaggle imported
- All have `sources.kaggle` with analytics
- Congestion risk and orbital band populated

✅ **Phase 3 Success**:
- 5,000+ satellites have `sources.satnogs` data
- Operational status reflects ground observations
- Transmitter data populated for active satellites

✅ **Overall Success**:
- Database has 20,000+ satellites (growth from 17,791)
- Multi-source coverage for majority of active satellites
- Launch date 2025-12-07 exists in database
- No duplicate NORAD IDs
- All canonical fields promoted correctly

---

## Next Steps

1. ✅ **Complete this analysis** (DONE)
2. ⏭️ Create GCAT import script (`scripts/import/import_gcat_launches.py`)
3. ⏭️ Run GCAT import and verify
4. ⏭️ Run Kaggle import with existing script
5. ⏭️ Create SatNOGS import script
6. ⏭️ Run SatNOGS import (long-running)
7. ⏭️ Comprehensive verification and reporting

---

**Analysis Complete**: Ready to proceed with Phase 1 implementation

# Technical Specification: Update Satellite Launch Data

## Task Summary

**Problem**: The satellite registry data in the database is outdated. The most recent launch date in the current data is 2025-09-13, but launches have occurred as recently as 2025-12-07.

**Goal**: Fetch and import more recent satellite launch data from UNOOSA (United Nations Office for Outer Space Affairs) into the ArangoDB database.

---

## Difficulty Assessment

**Medium** - This task requires:
- Understanding the UNOOSA data source and export mechanism
- Creating or modifying scripts to fetch fresh data
- Ensuring data integrity during import
- Handling potential data format changes
- Verifying successful import without data loss

---

## Current State Analysis

### Data Sources

### Available Sources (Ranked by Currentness)

1. **GCAT (General Catalog)** - ✅ BEST FOR RECENT DATA
   - **File**: `gcat_satcat.tsv` (18.2 MB, already downloaded)
   - **Updated**: Feb 15, 2026
   - **Coverage**: Through Jan 11, 2026
   - **Format**: TSV (tab-separated)
   - **Recent launches**: 99 satellites from Dec 2025 onward
   - **Source**: Jonathan McDowell (planet4589.org/space/gcat)

2. **UNOOSA (UN Registry)** - Official but delayed
   - **Files**: 
     - `data/unoosa_registry.csv` (5,401 records)
     - `data/unoosa_registry_with_norad.csv` (with NORAD enrichment)
   - **Updated**: Unknown (most recent launch: Sept 13, 2025)
   - **Gap**: Missing ~3 months of data
   - **Source**: https://www.unoosa.org/oosa/osoindex/search-ng.jspx

3. **CelesTrak** - TLE orbital elements (not launch registry)
   - Real-time orbital data, not comprehensive launch registry
   
4. **Space-Track** - TLE data (requires authentication)
   - Requires credentials, focuses on orbital elements
   
5. **SatNOGS** - Operational status and telemetry ✨
   - **API**: https://db.satnogs.org/api/
   - **Real-time data**: Operational status from ground station observations
   - **Unique data**: Transmitter frequencies, telemetry, decay confirmation
   - **Community-verified**: Crowdsourced observations
   
6. **Kaggle** - Orbital analytics and derived metrics ✨
   - **File**: `/Users/frankblau/Downloads/current_catalog.csv` (14,623 satellites)
   - **Updated**: Feb 16, 2026 (yesterday!)
   - **Source**: CelesTrak TLE data with analytics
   - **Unique data**: Pre-calculated orbit categories, congestion risk, altitude bands
   - **Coverage**: Very comprehensive (3x more than UNOOSA)

### Current Data Status
- **Most recent launch**: 2025-09-13 (September 13, 2025)
- **Missing data**: Launches from September 14, 2025 to at least December 7, 2025
- **Gap**: Approximately 3 months of satellite launch data

### Existing Import Infrastructure
- **Database**: ArangoDB (collection: `satellites`)
- **Import Scripts**:
  - `scripts/import/import_arangodb_data.py` - Imports from JSON/CSV to ArangoDB
  - Various enrichment scripts in `scripts/maintenance/`
- **Data Structure**: Multi-source document model with:
  - `sources.unoosa` - UNOOSA registry data
  - `canonical` - Normalized/promoted fields
  - `metadata` - Tracking and transformation info

---

## Technical Context

### Language & Dependencies
- **Language**: Python 3.11+
- **Key Libraries**:
  - `arango` (python-arango) - ArangoDB client
  - `requests` - HTTP client for web requests
  - `beautifulsoup4` - HTML parsing (if needed for scraping)
  - `pandas` - CSV manipulation
  - `json` - Data serialization

### Database Configuration
- **Database**: ArangoDB (kessler)
- **Collection**: `satellites`
- **Connection**: Configured via environment variables
  - `ARANGO_HOST` (default: http://localhost:8529)
  - `ARANGO_USER` (default: root)
  - `ARANGO_PASSWORD`

---

## Implementation Approach

### Recommended Strategy: GCAT + UNOOSA + SatNOGS + Kaggle (Multi-Source)

Use both data sources to get comprehensive and current data:

#### Phase 1: Import Recent Launches from GCAT ✅

**GCAT provides the most current launch data**:
- **Updated**: Feb 15, 2026
- **Coverage**: Launches through Jan 11, 2026
- **Recent Data**: 99 satellites launched Dec 2025 or later
- **Location**: `gcat_satcat.tsv` (18.2 MB, already downloaded)

**Steps**:
1. **Parse GCAT Data**:
   - Script: `scripts/import/import_gcat_launches.py`
   - Parse TSV format (tab-delimited)
   - Extract: Launch date, Name, NORAD ID, Owner, State, orbital params
   - Filter for launches after 2025-09-13

2. **Match and Merge**:
   - Match by NORAD ID (primary), international designator (secondary)
   - Update existing records: Add `sources.gcat` data
   - Create new records for unknown satellites
   - Preserve existing `sources.unoosa` data

3. **Import to ArangoDB**:
   - Upsert operation (update or insert)
   - Maintain multi-source document structure
   - Update canonical fields

#### Phase 2: Supplement with UNOOSA Registration Data (Optional)

**UNOOSA provides official registration details** not in GCAT:

**Steps**:
1. **Check for Updated UNOOSA Data**:
   - Visit UNOOSA Online Index
   - Search for satellites launched Sept-Dec 2025
   - Export any newly registered satellites

2. **Merge Registration Data**:
   - Script: `scripts/import/merge_unoosa_updates.py`
   - Match UNOOSA records to existing satellites (by intl designator, NORAD ID)
   - Add/update `sources.unoosa` with official registration info
   - Particularly valuable for:
     - Registration documents
     - Official function descriptions
     - Launch site details
     - Legal registration status

#### Phase 3: Enrich with SatNOGS Operational Data (Recommended)

**SatNOGS provides real-time operational status** from ground station observations:

**Steps**:
1. **Fetch from SatNOGS API**:
   - Script: `scripts/import/import_satnogs_status.py`
   - Query API: `https://db.satnogs.org/api/satellites/`
   - Match by NORAD ID to existing records

2. **Enrich with Operational Data**:
   - Add `sources.satnogs` with:
     - Operational status (alive/dead/re-entered)
     - Transmitter frequencies and modes
     - Last observation date
     - Operator and website info
     - Telemetry availability

**Value**: Know which satellites are actually operational vs just cataloged

#### Phase 4: Import Kaggle Orbital Analytics (High Value)

**Kaggle provides pre-calculated analytics** not available elsewhere:

**Steps**:
1. **Import from Kaggle CSV**:
   - Script: `scripts/import/import_kaggle_catalog.py` (already exists!)
   - File: `/Users/frankblau/Downloads/current_catalog.csv`
   - Match by NORAD ID to existing records

2. **Enrich with Analytics**:
   - Add `sources.kaggle` with:
     - Altitude category and orbital band
     - Congestion risk assessment
     - Orbit lifetime category
     - Current orbital state (epoch)
     - Constellation membership

**Value**: Risk assessment and orbital analytics for all satellites

#### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Phase 1: GCAT Import                     │
│  GCAT (gcat_satcat.tsv) → Parse & Match → ArangoDB          │
│  • Add sources.gcat to existing records                     │
│  • Create new records for unknown satellites                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Phase 2: UNOOSA Supplementation                │
│  UNOOSA Export → Match by intl designator → ArangoDB        │
│  • Add sources.unoosa with registration details             │
│  • Enrich with official function descriptions               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Phase 3: SatNOGS Enrichment                    │
│  SatNOGS API → Match by NORAD ID → ArangoDB                 │
│  • Add sources.satnogs with operational status              │
│  • Enrich with transmitter and telemetry data               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Phase 4: Kaggle Analytics Import               │
│  Kaggle CSV → Match by NORAD ID → ArangoDB                  │
│  • Add sources.kaggle with orbital analytics                │
│  • Enrich with congestion risk and orbit categories         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Final: Multi-Source Documents                  │
│  ├─ sources.gcat (technical specs & launch data)            │
│  ├─ sources.unoosa (official registration)                  │
│  ├─ sources.satnogs (operational status)                    │
│  ├─ sources.kaggle (orbital analytics)                      │
│  └─ canonical (promoted/unified fields)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Source Code Structure Changes

### New Files

1. **`scripts/import/import_gcat_launches.py`** (PRIMARY)
   - Function: `parse_gcat_tsv(tsv_path, after_date=None)`
   - Function: `extract_launch_data(gcat_row)`
   - Function: `match_to_existing(gcat_record, collection)`
   - Function: `merge_gcat_data(existing_doc, gcat_data)`
   - Function: `import_gcat_to_arangodb(tsv_path, after_date)`
   
   **GCAT TSV Column Mapping**:
   - Column 7 (LDate): Launch date
   - Column 1 (JCAT): GCAT internal ID
   - Column 2 (Satcat): NORAD catalog number
   - Column 6 (Name): Satellite name
   - Column 15 (Owner): Owner organization code
   - Column 16 (State): Country/state code
   - Columns 33-37: Orbital parameters

2. **`scripts/import/merge_unoosa_updates.py`** (OPTIONAL - if UNOOSA update needed)
   - Function: `load_existing_data(csv_path)`
   - Function: `load_update_data(update_csv_path)`
   - Function: `merge_datasets(existing, updates)`
   - Function: `deduplicate_records(records)`
   - Function: `save_merged_data(records, output_path)`

3. **`scripts/import/import_satnogs_status.py`** (RECOMMENDED - operational status)
   - Function: `fetch_satnogs_satellite(norad_id)`
   - Function: `fetch_satnogs_transmitters(norad_id)`
   - Function: `merge_satnogs_data(existing_doc, satnogs_data)`
   - Function: `import_satnogs_to_arangodb()`
   
   **API Usage**:
   - GET `https://db.satnogs.org/api/satellites/?norad_cat_id={norad_id}`
   - GET `https://db.satnogs.org/api/transmitters/?satellite__norad_cat_id={norad_id}`

### Modified Files

Potentially:
- `data/unoosa_registry.csv` - Updated with new records
- `data/unoosa_registry_with_norad.csv` - Updated after NORAD enrichment
- Existing import scripts if refactoring is needed

---

## Data Model Changes

No database schema changes required. The existing multi-source document structure supports incremental updates:

```python
{
  "identifier": "NORAD-60123",  # Unique ID
  "sources": {
    "gcat": {
      "jcat_id": "S67890",
      "norad_cat_id": 60123,
      "launch_date": "2025 Dec 15",
      "name": "Example Sat",
      "mass_kg": 250,
      "owner": "EXAMPLECO",
      "state": "US",
      "perigee_km": 500,
      "apogee_km": 520,
      "inclination_deg": 97.5,
      # ... other GCAT technical fields
    },
    "unoosa": {
      "registration_number": "3850-2025-020",
      "international_designator": "2025-020A",
      "object_name": "Example Satellite",
      "country_of_origin": "USA",
      "date_of_launch": "2025-12-15",
      "function": "Earth observation",
      "launch_vehicle": "Falcon 9",
      "place_of_launch": "Cape Canaveral",
      "status": "in orbit",
      "registration_document": "/osoindex/...",
      # ... other UNOOSA registration fields
    },
    "satnogs": {
      "sat_id": "ABCD-1234-5678-9012-3456",
      "status": "alive",
      "deployed": "2025-12-15T14:30:00Z",
      "operator": "Example Corp",
      "website": "https://example.com/sat",
      "transmitters": [
        {"frequency": 437500000, "mode": "BPSK", "description": "Beacon"}
      ],
      "last_observation": "2026-02-17T12:00:00Z",
      # ... other SatNOGS operational fields
    },
    "kaggle": {
      "norad_cat_id": 60123,
      "object_type": "PAYLOAD",
      "satellite_constellation": "Example Constellation",
      "altitude_km": 510.5,
      "altitude_category": "Low LEO",
      "orbital_band": "LEO-Polar",
      "congestion_risk": "MEDIUM",
      "inclination": 97.5,
      "eccentricity": 0.001,
      "orbit_lifetime_category": "1-5yr",
      "mean_motion": 15.2,
      "epoch": "2026-02-16 14:00:00",
      "snapshot_date": "2026-02-16",
      # ... other Kaggle analytics fields
    }
  },
  "canonical": {
    "launch_date": "2025-12-15",
    "name": "Example Sat",
    "norad_cat_id": 60123,
    "country": "United States",
    "operator": "Example Corp",
    "status": "operational",  # Promoted from SatNOGS
    "perigee_km": 500,
    "apogee_km": 520,
    "inclination": 97.5,
    "altitude_km": 510.5,  # From Kaggle
    "orbital_band": "LEO-Polar",  # From Kaggle
    "congestion_risk": "MEDIUM",  # From Kaggle analytics
    # ... promoted fields from all sources
  },
  "metadata": {
    "sources_available": ["gcat", "unoosa", "satnogs", "kaggle"],
    "last_updated_at": "2026-02-17T14:35:00Z",
    "transformations": [...]
  }
}
```

---

## Implementation Steps

### Step 1: Investigate UNOOSA Export API
- Research export functionality on UNOOSA website
- Document API endpoints or export process
- Test data retrieval for recent launches

### Step 2: Create Data Fetch/Download Script
- Implement automated fetch (Option 1) OR manual download helper (Option 2)
- Add date range filtering
- Validate downloaded data

### Step 3: Create Merge Script
- Load existing CSV data
- Load new/updated CSV data
- Deduplicate based on `Registration Number` and `International Designator`
- Merge datasets preserving existing enrichments
- Save merged data to CSV

### Step 4: Import to ArangoDB
- Use existing import infrastructure
- Update existing records if they exist
- Insert new records
- Track import statistics

### Step 5: Run Enrichment Scripts
- Run NORAD enrichment if applicable
- Run launch data enrichment
- Update canonical fields

---

## Verification Approach

### Pre-Import Verification
1. **Data Completeness**:
   ```bash
   # Check record count
   wc -l data/unoosa_registry_update.csv
   
   # Verify date range
   awk -F',' 'NR>1 {print $5}' data/unoosa_registry_update.csv | sort -u
   ```

2. **Data Quality**:
   ```bash
   # Check for required fields
   python3 -c "
   import pandas as pd
   df = pd.read_csv('data/unoosa_registry_update.csv')
   print('Columns:', df.columns.tolist())
   print('Null counts:', df.isnull().sum())
   "
   ```

### Post-Import Verification
1. **Database Count**:
   ```python
   # Query ArangoDB for total count
   from database import connect_arangodb, db
   connect_arangodb()
   count = db.collection('satellites').count()
   print(f"Total satellites: {count}")
   ```

2. **Recent Launch Verification**:
   ```python
   # Query for launches after 2025-09-13
   query = """
   FOR doc IN satellites
     FILTER doc.canonical.launch_date >= "2025-09-14"
     SORT doc.canonical.launch_date DESC
     LIMIT 20
     RETURN {
       id: doc.identifier,
       name: doc.sources.unoosa.object_name,
       launch_date: doc.canonical.launch_date,
       country: doc.canonical.country
     }
   """
   cursor = db.aql.execute(query)
   for sat in cursor:
       print(sat)
   ```

3. **Data Integrity**:
   - Verify no duplicate records
   - Check that existing records weren't corrupted
   - Confirm new records have proper structure

### Test Commands
```bash
# Run import script
python3 scripts/import/import_unoosa_updates.py --verify

# Check latest launch date
python3 scripts/verification/verify_update.py --check-latest

# Verify data quality
python3 scripts/verification/check_pretty.py
```

---

## Risk Mitigation

### Risks
1. **UNOOSA Export Format Change**: Data structure may differ from current CSV
2. **Data Loss**: Import could overwrite existing enrichments
3. **Duplicates**: Same satellite registered multiple times
4. **API Rate Limiting**: If using automated fetch

### Mitigation Strategies
1. **Backup**: Create backup of `satellites` collection before import
2. **Dry Run**: Test import with `--dry-run` flag first
3. **Incremental Import**: Import in batches, verify after each batch
4. **Validation**: Check data structure before bulk import

---

## Success Criteria

1. ✅ **GCAT Import**: Database contains launches through Jan 11, 2026 (99+ new satellites)
2. ✅ **Data Integrity**: All original 5,401 records preserved, no data loss
3. ✅ **Multi-Source**: Records have appropriate source data (GCAT, UNOOSA, SatNOGS, Kaggle)
4. ✅ **Canonical Fields**: Properly promoted from all sources (launch date, status, analytics)
5. ✅ **Kaggle Analytics**: 14,623 satellites enriched with orbit categories and congestion risk
6. ✅ **Operational Status**: SatNOGS data shows which satellites are actually active
7. ✅ **Repeatability**: Import process documented with scripts for future updates
8. ✅ **Verification**: All checks pass (counts, dates, integrity)

---

## Dependencies

### Python Packages
```txt
arango>=7.5.0
requests>=2.31.0
pandas>=2.0.0
beautifulsoup4>=4.12.0  # If web scraping needed
```

### External Services
- **GCAT**: https://planet4589.org/space/gcat (data already downloaded)
- **ArangoDB** instance (local or remote)
- **UNOOSA** (optional): https://www.unoosa.org/oosa/osoindex/search-ng.jspx

### Environment Variables
```bash
ARANGO_HOST=http://localhost:8529
ARANGO_USER=root
ARANGO_PASSWORD=kessler_dev_password
```

---

## Timeline Estimate

- **GCAT Analysis** (understand TSV format, column mapping): 30 minutes
- **Script Development** (parse/match/import): 2-3 hours
- **Testing & Verification**: 1 hour
- **Total**: 3-4 hours

**Note**: Much faster than UNOOSA approach since data is already downloaded and well-documented

---

## Notes

### Multi-Source Strategy: GCAT + UNOOSA

**Best Approach**: Use **both sources** for complementary data

#### GCAT (Primary for Recent Launches)
**Use for**:
- ✅ Recent launch data (Sept 2025 - Jan 2026)
- ✅ Comprehensive coverage (all space objects)
- ✅ Technical data (mass, dimensions, orbital parameters)
- ✅ Already downloaded and up-to-date

**Provides**:
- Launch dates
- NORAD catalog IDs
- Object names and types
- Country/owner codes
- Physical characteristics
- Orbital parameters

#### UNOOSA (Primary for Registration Data)
**Use for**:
- ✅ Official UN registration information
- ✅ Registration documents and legal details
- ✅ Launch site information
- ✅ Function/purpose descriptions
- ✅ Status updates (operational, decayed, etc.)

**Provides**:
- Registration numbers
- International designators
- Official country of origin
- Launch vehicle details
- Place of launch
- Function descriptions
- Registration document links
- UN registered status

#### SatNOGS (For Operational Status & Communications)
**Use for**:
- ✅ **Real-time operational status** (alive, dead, re-entered)
- ✅ Radio transmitter data (frequencies, modes)
- ✅ Telemetry from ground station observations
- ✅ Community-verified satellite activity
- ✅ Actual decay dates (not predicted)

**Provides**:
- Operational status (from observations, not estimates)
- Transmitter frequencies and modes
- Deployment dates (vs just launch dates)
- Telemetry data and observation counts
- Website and operator information
- Associated satellites relationships
- Frequency violation flags

**API**: Public REST API at `https://db.satnogs.org/api/satellites/`

#### Kaggle (For Orbital Analytics)
**Use for**:
- ✅ **Pre-calculated orbital analytics** (altitude categories, congestion risk)
- ✅ Comprehensive coverage (14,623 satellites, 3x more than UNOOSA)
- ✅ Current orbital state (updated daily from CelesTrak)
- ✅ Derived metrics not available elsewhere

**Provides**:
- Altitude category (Very Low, Low, Medium LEO, etc.)
- Orbital band classification (LEO-Polar, LEO-Equatorial, MEO, GEO)
- Congestion risk level (LOW, MEDIUM, HIGH)
- Orbit lifetime category (<1yr, 1-5yr, >5yr)
- Current altitude, eccentricity, inclination
- Constellation membership
- Country of origin

**File**: `/Users/frankblau/Downloads/current_catalog.csv`
**Updated**: Daily (latest: Feb 16, 2026)

#### Complementary Nature
- **GCAT**: Comprehensive catalog with launch data and technical specs
- **UNOOSA**: Official UN registration and legal details
- **SatNOGS**: Real-time operational status from observations
- **Kaggle**: Orbital analytics and risk assessment
- **Together**: Complete picture - launches + legal + operational + analytics

### Future Updates

**Regular Update Workflow**:

1. **Weekly/Monthly**: Update GCAT data (most current)
   ```bash
   wget https://planet4589.org/space/gcat/tsv/cat/satcat.tsv -O gcat_satcat.tsv
   python3 scripts/import/import_gcat_launches.py --after-date 2026-01-11
   ```

2. **Quarterly**: Check UNOOSA for new registrations
   - Many satellites are registered months after launch
   - UNOOSA provides official legal details GCAT doesn't have
   - Export and merge new registration data

3. **Automated**: Set up cron job for GCAT updates
   ```bash
   # Weekly GCAT update (Sundays at 2 AM)
   0 2 * * 0 cd /path/to/kessler && ./scripts/update_gcat.sh
   ```

**Benefits of Multi-Source Approach**:
- ✅ **Most current launch data** (GCAT - through Jan 2026)
- ✅ **Official registration** (UNOOSA - legal documentation)
- ✅ **Real operational status** (SatNOGS - community observations)
- ✅ **Orbital analytics** (Kaggle - congestion risk, orbit categories)
- ✅ **Comprehensive coverage** (14,623 satellites from Kaggle)
- ✅ **Redundancy and validation** (cross-check data across sources)

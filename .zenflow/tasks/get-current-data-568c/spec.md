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
   
5. **Kaggle** - Curated satellite catalog
   - May not be most current

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

### Primary Approach: Use GCAT (General Catalog) - RECOMMENDED ✅

**GCAT is the best source** for current satellite launch data:
- **Updated**: Feb 15, 2026 (much more current than UNOOSA)
- **Coverage**: Launches through Jan 11, 2026
- **Recent Data**: 99 satellites launched Dec 2025 or later
- **Format**: TSV (tab-separated values)
- **Location**: Already downloaded at `gcat_satcat.tsv` (18.2 MB)
- **Source**: Jonathan McDowell's comprehensive catalog (planet4589.org/space/gcat)

**Steps**:
1. **Parse GCAT Data**:
   - Script: `scripts/import/import_gcat_launches.py`
   - Parse TSV format (tab-delimited)
   - Extract fields: Launch date, Name, NORAD ID, Owner, State, etc.
   - Filter for launches after 2025-09-13

2. **Match and Merge**:
   - Match GCAT records to existing database records by:
     - NORAD catalog ID (primary key)
     - International designator
     - Object name
   - Enrich existing records with GCAT data
   - Create new records for satellites not in database

3. **Import to ArangoDB**:
   - Update existing documents with new GCAT source data
   - Insert new documents for previously unknown satellites
   - Preserve existing enrichments (UNOOSA, etc.)
   - Update canonical fields

### Alternative: UNOOSA Update (If official UN data needed)

If official UNOOSA registration data is required:

**Steps**:
1. **Download from UNOOSA**:
   - Manual export from https://www.unoosa.org/oosa/osoindex/search-ng.jspx
   - Filter by launch date >= 2025-09-14
   - Export to CSV

2. **Merge Script**:
   - Script: `scripts/import/merge_unoosa_updates.py`
   - Merge with existing `data/unoosa_registry.csv`
   - Preserve NORAD enrichments

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
  "identifier": "3834-2025-015",  # Unique ID
  "sources": {
    "unoosa": {
      "registration_number": "3834-2025-015",
      "international_designator": "2025-207A",
      "object_name": "Example Satellite",
      "country_of_origin": "USA",
      "date_of_launch": "2025-12-07",  # New data
      "function": "Earth observation",
      "status": "in orbit",
      # ... other UNOOSA fields
    }
  },
  "canonical": {
    "launch_date": "2025-12-07",
    "country": "United States",
    # ... promoted fields
  },
  "metadata": {
    "sources_available": ["unoosa"],
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

1. ✅ Database contains launches up to at least 2025-12-07
2. ✅ No data loss - all original 5,401 records preserved
3. ✅ New records properly formatted with UNOOSA source data
4. ✅ Canonical fields updated for new records
5. ✅ Import process documented and repeatable
6. ✅ Verification scripts pass all checks

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

### Why GCAT Instead of UNOOSA?

**GCAT Advantages**:
- ✅ **3+ months more current** (Jan 2026 vs Sept 2025)
- ✅ **Already downloaded** - no web scraping needed
- ✅ **Well-documented** format with clear column definitions
- ✅ **Comprehensive** - includes all space objects, not just UN-registered
- ✅ **Maintained by expert** (Jonathan McDowell, recognized authority)
- ✅ **Free and open** under CC-BY-4.0 license

**UNOOSA Limitations**:
- ⚠️ Significant lag (3+ months behind actual launches)
- ⚠️ Only includes officially registered satellites (many are not registered)
- ⚠️ No public API - requires web scraping or manual export
- ⚠️ Export mechanism may change

### Future Updates

- **GCAT** is updated regularly (latest: Feb 15, 2026)
- Download fresh GCAT data: `wget https://planet4589.org/space/gcat/tsv/cat/satcat.tsv`
- Re-run import script to get latest launches
- Consider setting up periodic automated updates (weekly/monthly)
- Document the process for future maintainers

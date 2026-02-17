# Spec and build

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:
- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 51935bae-7aa1-432b-b07e-2335999635f7 -->

**Difficulty**: Medium

**Summary**: The satellite registry data is outdated (most recent: 2025-09-13). Need to fetch and import launches through at least 2025-12-07 from UNOOSA.

**Technical Specification**: See `spec.md` for complete details.

**Key Findings**:
- Current data has 5,401 records with most recent launch on 2025-09-13
- Missing ~3 months of satellite launch data (Sept-Dec 2025)
- UNOOSA Online Index has export functionality that can be leveraged
- Existing import infrastructure can be reused with modifications

---

### [ ] Step: Analyze GCAT Data and Plan Import

**Objective**: Understand GCAT data structure and plan the import strategy.

**Primary Data Source**: GCAT (General Catalog) - **Already Downloaded**
- File: `gcat_satcat.tsv` (18.2 MB)
- Updated: Feb 15, 2026
- Coverage: Launches through Jan 11, 2026
- Contains: 99 satellites launched Dec 2025 or later

**Tasks**:
- [ ] Examine GCAT TSV structure and column mapping
- [ ] Identify key fields for matching (NORAD ID, intl designator, name)
- [ ] Test parsing a subset of GCAT data
- [ ] Determine matching strategy (NORAD ID primary, name fallback)
- [ ] Plan handling of satellites not yet in database

**Verification**:
- Successfully parse sample GCAT records
- Extract launch date, NORAD ID, name, country for recent satellites
- Verify 99 satellites with launch dates >= 2025-09-14

**Output**: Understanding of GCAT structure and matching approach

---

### [ ] Step: Create GCAT Import Script

**Objective**: Build script to parse GCAT data and import recent launches to ArangoDB.

**Tasks**:
- [ ] Create `scripts/import/import_gcat_launches.py`
- [ ] Implement TSV parser for GCAT format
- [ ] Extract relevant fields (date, NORAD ID, name, country, orbital params)
- [ ] Filter for launches after 2025-09-13
- [ ] Implement matching logic:
  - Primary: Match by NORAD catalog ID
  - Secondary: Match by international designator
  - Fallback: Match by name similarity
- [ ] Handle merge scenarios:
  - Update existing records with GCAT source data
  - Create new records for unknown satellites
  - Preserve existing source data (UNOOSA, etc.)

**Implementation Details**:
- Parse GCAT date format: "YYYY MMM DD"
- Extract NORAD ID from column 2 (Satcat)
- Extract country code from column 16 (State)
- Add logging for matched vs new records
- Dry-run mode for testing

**Verification**:
- Test parsing with 10 sample records
- Verify date filtering works correctly
- Test matching against existing database records
- Validate no data corruption

**Output**: 
- Working `import_gcat_launches.py` script
- Successfully parsed GCAT records ready for import

---

### [ ] Step: Import to ArangoDB and Enrich

**Objective**: Import new data into ArangoDB and run enrichment pipelines.

**Tasks**:
- [ ] Create database backup before import
- [ ] Run import with dry-run flag first
- [ ] Import new/updated records to ArangoDB
- [ ] Run NORAD enrichment if applicable
- [ ] Run launch data enrichment scripts
- [ ] Update canonical fields for new records

**Implementation Details**:
- Use existing `scripts/import/import_arangodb_data.py` or create new script
- Implement upsert logic (update existing, insert new)
- Track import statistics (new vs updated records)
- Handle errors gracefully

**Verification**:
- Query database for record count (should be > 5,401)
- Verify launches after 2025-09-13 exist
- Check specific launch on 2025-12-07 is present
- Run data integrity checks
- Verify canonical fields are properly populated

**Commands**:
```bash
# Import to ArangoDB
python3 scripts/import/import_arangodb_data.py

# Enrich data
python3 scripts/maintenance/enrich_launch_data.py

# Verify
python3 scripts/verification/verify_update.py --check-latest
```

**Output**: 
- Updated ArangoDB database with recent launches
- Import report with statistics

---

### [ ] Step: Verification and Documentation

**Objective**: Verify the import was successful and document the process for future updates.

**Tasks**:
- [ ] Run comprehensive verification checks
- [ ] Verify specific launches from Sept-Dec 2025 are present
- [ ] Check data integrity (no duplicates, no data loss)
- [ ] Verify canonical field promotion worked correctly
- [ ] Document the entire process and any issues encountered
- [ ] Create report summarizing what was done

**Verification Commands**:
```bash
# Check total record count
python3 -c "from database import connect_arangodb, db; connect_arangodb(); print(f'Total: {db.collection(\"satellites\").count()}')"

# Check for recent launches
python3 scripts/verification/verify_update.py --check-latest --after-date 2025-09-13

# Data integrity checks
python3 scripts/verification/check_pretty.py
```

**Expected Results**:
- Database has > 5,401 records
- Launches from Sept-Dec 2025 are present
- Launch date 2025-12-07 exists in database
- No duplicate records
- Canonical fields properly populated

**Documentation**:
- Write implementation report to `report.md`
- Include:
  - Data source and export method used
  - Number of new records imported
  - Any issues or challenges encountered
  - Commands for future updates
  - Verification results

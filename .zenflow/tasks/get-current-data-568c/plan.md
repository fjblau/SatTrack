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

### [ ] Step: Investigate UNOOSA Data Export

**Objective**: Determine the best method to fetch recent UNOOSA satellite registry data.

**Tasks**:
- [ ] Access UNOOSA Online Index (https://www.unoosa.org/oosa/osoindex/search-ng.jspx)
- [ ] Use browser dev tools to inspect the export/download functionality
- [ ] Identify API endpoints or export format (CSV, JSON, XML)
- [ ] Test export with date filter (launches after 2025-09-13)
- [ ] Document the export process and any authentication requirements

**Verification**:
- Successfully export a sample dataset
- Verify exported data format matches existing CSV structure
- Confirm export includes launches from Sept-Dec 2025

**Output**: Documentation of export process in implementation notes

---

### [ ] Step: Create Data Fetch and Merge Scripts

**Objective**: Build scripts to fetch new UNOOSA data and merge it with existing records.

**Tasks**:
- [ ] Create `scripts/import/fetch_unoosa_data.py` (if automated) or document manual process
- [ ] Create `scripts/import/merge_unoosa_updates.py` to merge new data with existing CSV
- [ ] Implement deduplication based on Registration Number and International Designator
- [ ] Add data validation (required fields, date format, etc.)
- [ ] Create backup of existing CSV before merge

**Implementation Details**:
- Support filtering by date range
- Preserve existing enrichments (NORAD IDs, etc.)
- Handle edge cases (missing fields, format changes)
- Add logging and error handling

**Verification**:
- Test script with sample data
- Verify no data loss in merge
- Check for proper duplicate detection
- Validate merged CSV structure

**Output**: 
- Working fetch/merge scripts
- Updated CSV with new launch data

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

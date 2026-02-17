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

**Summary**: The satellite registry data is outdated (most recent: 2025-09-13). Need to import launches through at least 2025-12-07 and enrich with multi-source data.

**Technical Specification**: See `spec.md` for complete details.

**Key Findings**:
- Current data has 5,401 records with most recent launch on 2025-09-13
- Missing ~3 months of satellite launch data (Sept-Dec 2025)
- **Four complementary data sources available**:
  - **GCAT**: 99 recent satellites (Dec 2025 - Jan 2026) - already downloaded
  - **UNOOSA**: Official UN registration data (delayed but authoritative)
  - **SatNOGS**: Real-time operational status via API
  - **Kaggle**: 14,623 satellites with orbital analytics - updated Feb 16, 2026
- Existing import infrastructure can be reused (Kaggle script already exists!)

---

### [x] Step: Analyze Data Sources and Plan Multi-Source Import
<!-- chat-id: 6718f161-3018-4bb8-94f3-2dea4abc0702 -->

**Objective**: Understand all four data sources and plan the comprehensive import strategy.

**Available Data Sources**:

1. **GCAT** (General Catalog) - Recent launches & tech specs
   - File: `gcat_satcat.tsv` (18.2 MB, already downloaded)
   - Updated: Feb 15, 2026
   - Coverage: 99 satellites launched Dec 2025 - Jan 2026

2. **Kaggle** - Orbital analytics (14,623 satellites)
   - File: `/Users/frankblau/Downloads/current_catalog.csv`
   - Updated: Feb 16, 2026 (yesterday!)
   - Script: `scripts/import/import_kaggle_catalog.py` (already exists!)

3. **SatNOGS** - Operational status
   - API: `https://db.satnogs.org/api/satellites/`
   - Real-time data

4. **UNOOSA** - Official registration (optional)
   - Will check for new registrations

**Tasks**:
- [ ] Examine GCAT TSV structure and column mapping
- [ ] Review Kaggle CSV structure and existing import script
- [ ] Test SatNOGS API endpoint
- [ ] Determine matching strategy across sources (NORAD ID primary)
- [ ] Plan handling of new satellites vs enriching existing ones
- [ ] Decide on import order (GCAT → Kaggle → SatNOGS → UNOOSA)

**Verification**:
- Successfully parse sample records from GCAT and Kaggle
- Test SatNOGS API with a known NORAD ID
- Verify data freshness across all sources

**Output**: Understanding of all data sources and matching approach

---

### [x] Step: Phase 1 - Import GCAT Launch Data
<!-- chat-id: fdaf1ee4-684f-4bb6-a04b-f9b2587a7bb2 -->

**Objective**: Import 99 recent satellite launches (Dec 2025 - Jan 2026) from GCAT.

**Tasks**:
- [ ] Create `scripts/import/import_gcat_launches.py`
- [ ] Implement TSV parser for GCAT format
- [ ] Extract relevant fields (date, NORAD ID, name, country, orbital params)
- [ ] Filter for launches after 2025-09-13
- [ ] Implement matching logic:
  - Primary: Match by NORAD catalog ID
  - Secondary: Match by international designator
  - Fallback: Create new record
- [ ] Handle merge scenarios:
  - Update existing records: Add `sources.gcat`
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
- Confirm 99+ new satellites imported

**Output**: 
- Working `import_gcat_launches.py` script
- Database updated with recent launches through Jan 2026

---

### [x] Step: Phase 2 - Import Kaggle Orbital Analytics
<!-- chat-id: 3d93c078-4192-44f8-8fa5-b4eae5af3e12 -->

**Objective**: Enrich all satellites with orbital analytics from Kaggle (14,623 satellites).

**Tasks**:
- [ ] Use existing `scripts/import/import_kaggle_catalog.py`
- [ ] Run import with Kaggle CSV: `/Users/frankblau/Downloads/current_catalog.csv`
- [ ] Match records by NORAD ID
- [ ] Add `sources.kaggle` with:
  - Altitude category and orbital band
  - Congestion risk assessment
  - Orbit lifetime category
  - Current orbital state
  - Constellation membership

**Implementation Details**:
- Script already exists - just run it!
- Updates existing records, creates new for unknown NORAD IDs
- Preserves all existing source data

**Verification**:
- Verify records have `sources.kaggle` data
- Check congestion risk and orbital band fields populated
- Confirm 14,623 satellites processed
- Sample check: verify a recent satellite has analytics

**Commands**:
```bash
# Import Kaggle data
python3 scripts/import/import_kaggle_catalog.py /Users/frankblau/Downloads/current_catalog.csv
```

**Output**: 
- Database enriched with orbital analytics for 14K+ satellites
- Congestion risk and orbit categories available

---

### [ ] Step: Phase 3 - Enrich with SatNOGS Operational Status

**Objective**: Add real-time operational status for satellites.

**Tasks**:
- [ ] Create `scripts/import/import_satnogs_status.py`
- [ ] Query SatNOGS API for all satellites with NORAD IDs
- [ ] Add `sources.satnogs` with:
  - Operational status (alive/dead/re-entered)
  - Transmitter frequencies and modes
  - Last observation date
  - Operator and website
- [ ] Update canonical status field based on SatNOGS observations

**Implementation Details**:
- API endpoint: `https://db.satnogs.org/api/satellites/?norad_cat_id={id}`
- Match by NORAD ID
- Rate limit: reasonable (community API)
- Handle satellites not in SatNOGS (not all are tracked)

**Verification**:
- Verify records have `sources.satnogs` where available
- Check operational status reflects actual observations
- Confirm transmitter data populated for active satellites

**Commands**:
```bash
# Import SatNOGS status
python3 scripts/import/import_satnogs_status.py
```

**Output**: 
- Database enriched with real operational status
- Know which satellites are actually transmitting

---

### [ ] Step: Phase 4 (Optional) - Supplement with UNOOSA Registration

**Objective**: Add official UN registration information for recently launched satellites.

**Context**: UNOOSA provides official registration details:
- Registration documents and legal information
- Official function descriptions
- Launch vehicle and site details

**Tasks**:
- [ ] Check UNOOSA for newly registered satellites (Sept-Dec 2025)
- [ ] Export any new UNOOSA registration data if available
- [ ] Create merge script to add `sources.unoosa` to existing records
- [ ] Import registration data to ArangoDB
- [ ] Update canonical fields if needed

**Note**: Many satellites are registered months after launch, so this can be done later.

**Output**: Enhanced records with official UN registration data

---

### [ ] Step: Local Verification and Testing

**Objective**: Verify the local import was successful before deploying to production.

**Tasks**:
- [ ] Run comprehensive verification checks
- [ ] Verify specific launches from Sept-Dec 2025 are present
- [ ] Check data integrity (no duplicates, no data loss)
- [ ] Verify canonical field promotion worked correctly
- [ ] Test multi-source records (GCAT + UNOOSA where applicable)
- [ ] Document the entire process and any issues encountered
- [ ] Create report summarizing what was done

**Verification Commands**:
```bash
# Check total record count
python3 -c "from database import connect_arangodb, db; connect_arangodb(); print(f'Total: {db.collection(\"satellites\").count()}')"

# Check for recent launches
python3 scripts/verification/verify_update.py --check-latest --after-date 2025-09-13

# Verify GCAT source data
python3 -c "
from database import connect_arangodb, db
connect_arangodb()
count = db.aql.execute('FOR doc IN satellites FILTER doc.sources.gcat != null RETURN 1').count()
print(f'Records with GCAT data: {count}')
"

# Data integrity checks
python3 scripts/verification/check_pretty.py
```

**Expected Results**:
- **Record Count**: Database has ~15,000+ records (5,401 original + Kaggle expansion)
- **Recent Launches**: Launches from Sept 2025 - Jan 2026 present (99+ from GCAT)
- **Multi-Source Coverage**:
  - Records with `sources.gcat`: 99+ (recent launches)
  - Records with `sources.kaggle`: 14,623 (orbital analytics)
  - Records with `sources.satnogs`: Varies (actively tracked satellites)
  - Records with `sources.unoosa`: 5,401+ (original + new registrations)
- **Data Quality**:
  - Launch date 2025-12-07 exists in database
  - No duplicate records
  - Canonical fields properly promoted from all sources
  - Congestion risk and orbital band populated (from Kaggle)
  - Operational status reflects SatNOGS observations

**Next Steps**:
- If all verifications pass locally, proceed to production deployment
- If issues found, fix and re-verify before deploying

---

### [ ] Step: Production Deployment to Railway

**Objective**: Deploy the updated database to Railway production environment.

**Railway Connection**:
- **Host**: `https://arangodb-production-d6fb.up.railway.app:443`
- **Database**: `kessler`
- **User**: `root`
- **Password**: From `RAILWAY_PASSWORD` environment variable

**Tasks**:
- [ ] **Step 1: Backup Production Database**
  - Export current Railway database to JSONL
  - Store backup with timestamp
  - Verify backup integrity
  
- [ ] **Step 2: Export Local Database**
  - Run `scripts/import/export_arangodb.py`
  - Verify all collections exported
  - Check file sizes and record counts
  
- [ ] **Step 3: Import to Railway**
  - Set `RAILWAY_PASSWORD` environment variable
  - Run `scripts/import/import_to_railway.py`
  - Monitor import progress
  - Check for errors
  
- [ ] **Step 4: Verify Production Import**
  - Query production database for record counts
  - Verify recent launches present (2025-12-07+)
  - Check multi-source data (GCAT, Kaggle, SatNOGS)
  - Test API endpoints on production

**Commands**:
```bash
# Set Railway password
export RAILWAY_PASSWORD='your-railway-password'

# Export local database
python3 scripts/import/export_arangodb.py

# Import to Railway
python3 scripts/import/import_to_railway.py

# Verify production (from production API)
curl https://your-api.railway.app/v2/search?q=2025-12
```

**Safety Measures**:
- Backup created before any changes
- Dry-run verification on local copy
- Incremental import with error handling
- Rollback plan ready (restore from backup)

**Verification on Production**:
- Record count matches expected (~15,000+)
- Recent satellites searchable
- API returns data correctly
- No performance degradation

**Rollback Plan** (if issues):
```bash
# Restore from backup
python3 scripts/import/import_to_railway.py --restore-from backup_TIMESTAMP
```

**Output**: 
- Production database updated with multi-source data
- API serving current satellite information

---

### [ ] Step: Final Documentation

**Objective**: Document the complete process for future reference and updates.

**Tasks**:
- [ ] Write implementation report to `report.md`
- [ ] Document production deployment steps
- [ ] Create update guide for future data refreshes

**Documentation**:
- Write implementation report to `report.md`
- Include:
  - **Four-source strategy** used (GCAT + Kaggle + SatNOGS + UNOOSA)
  - Number of records from each source:
    - GCAT: 99+ recent launches
    - Kaggle: 14,623 satellites with analytics
    - SatNOGS: X satellites with operational status
    - UNOOSA: 5,401+ with registration data
  - Data quality and completeness by source
  - Value-add from each source (launches, analytics, status, registration)
  - **Production deployment** steps and verification
  - Any issues or challenges encountered
  - Commands for future updates of each source
  - Rollback procedure if needed
  - Verification results and statistics (local + production)

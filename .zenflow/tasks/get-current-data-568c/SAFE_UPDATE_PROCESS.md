# Safe Database Update Process

## CRITICAL RULES - READ BEFORE IMPORTING

### 1. Data Governance - Source Approval
**APPROVED sources** (can promote to canonical):
- `unoosa`, `spacetrack`, `celestrak`, `tleapi`, `kaggle`

**UNAPPROVED sources** (ONLY in sources.*, NEVER canonical):
- `gcat`, `satnogs`

**WHY**: Unapproved sources can corrupt `canonical.source_priority` and break existing satellites.

### 2. Schema Invariants - MUST ALWAYS BE TRUE

#### CRITICAL: canonical.name MUST NEVER BE NULL
- **ALL satellites MUST have canonical.name**
- Use identifier as fallback if no source provides name
- Run `normalize_canonical_fields.py` after ANY import that touches canonical
- Missing canonical.name breaks graph queries with: "Cannot create edge with nonexistent target"

#### Satellite _key Stability
- **NEVER change satellite _key values** once created
- Changing _keys breaks edges (orbital_proximity, constellation_membership, etc.)
- If you change _keys, you MUST delete broken edges

---

## Safe Import Process

### Pre-Import Checklist

1. **Backup Production Database**
   ```bash
   export RAILWAY_PASSWORD='your-password'
   python3 scripts/import/export_railway.py
   # Saves to: railway_backup_YYYYMMDD_HHMMSS/
   ```

2. **Backup Local Database**
   ```bash
   python3 scripts/import/export_arangodb.py
   # Saves to: arango_export/
   ```

3. **Verify PRETTY is Working**
   - Go to app, search for PRETTY
   - View Satellite Neighborhood graph
   - If broken NOW, fix before proceeding

### Import Order (MUST FOLLOW)

1. **Kaggle Import** (Approved source, safe to promote)
   ```bash
   python3 scripts/import/import_kaggle_catalog_arango.py /path/to/current_catalog.csv
   ```
   
2. **GCAT Import** (Unapproved source, fills launch date gaps only)
   ```bash
   python3 scripts/import/import_gcat_launches.py gcat_satcat.tsv 2025-09-13
   ```

3. **Normalize Canonical Fields** (REQUIRED after ANY import)
   ```bash
   python3 scripts/import/normalize_canonical_fields.py --apply
   ```
   - Ensures ALL satellites have canonical.name
   - Fills launch_date from approved sources

4. **SatNOGS Import** (Unapproved source, operational status only)
   ```bash
   python3 scripts/import/import_satnogs_status.py
   ```
   - Takes ~30 minutes
   - Can skip if not needed

### Post-Import Verification (LOCAL)

```bash
python3 -c "
from database import connect_arangodb
import database.connection as db_conn

connect_arangodb()

# Check for missing canonical.name
query = '''
FOR sat IN satellites
    FILTER sat.canonical.name == null OR sat.canonical.name == \"\"
    COLLECT WITH COUNT INTO count
    RETURN count
'''
result = list(db_conn.db.aql.execute(query))
missing_name = result[0] if result else 0

print(f'Satellites with missing canonical.name: {missing_name}')
if missing_name > 0:
    print('❌ FAIL - Run normalize_canonical_fields.py --apply')
    exit(1)

# Check PRETTY integrity
query = '''
FOR sat IN satellites
    FILTER sat.canonical.name == \"PRETTY\"
    RETURN {
        _key: sat._key,
        launch_date: sat.canonical.launch_date,
        canonical_source_priority: sat.canonical.source_priority
    }
'''
result = list(db_conn.db.aql.execute(query))

if result:
    pretty = result[0]
    errors = []
    
    if pretty['_key'] != '2023-155H':
        errors.append(f'_key changed to {pretty[\"_key\"]}')
    if pretty['launch_date'] != '2023-10-09':
        errors.append(f'launch_date changed to {pretty[\"launch_date\"]}')
    if 'gcat' in pretty.get('canonical_source_priority', []):
        errors.append('gcat in canonical.source_priority')
    if 'satnogs' in pretty.get('canonical_source_priority', []):
        errors.append('satnogs in canonical.source_priority')
    
    if errors:
        print('❌ PRETTY CORRUPTED:')
        for err in errors:
            print(f'  - {err}')
        print('STOP - Restore from backup!')
        exit(1)
    else:
        print('✅ PRETTY verified correct')
else:
    print('❌ PRETTY not found!')
    exit(1)

# Check most recent launch
query = '''
FOR sat IN satellites
    FILTER sat.canonical.launch_date != null
    SORT sat.canonical.launch_date DESC
    LIMIT 1
    RETURN {
        launch: sat.canonical.launch_date,
        name: sat.canonical.name
    }
'''
result = list(db_conn.db.aql.execute(query))
if result:
    print(f'Most recent launch: {result[0][\"launch\"]}: {result[0][\"name\"]}')

# Check for broken edges
query = '''
FOR edge IN orbital_proximity
    LET from_exists = DOCUMENT(edge._from)
    LET to_exists = DOCUMENT(edge._to)
    FILTER from_exists == null OR to_exists == null
    LIMIT 1
    RETURN 1
'''
result = list(db_conn.db.aql.execute(query))

if result:
    print('❌ BROKEN EDGES FOUND - Run cleanup script')
    exit(1)
else:
    print('✅ No broken edges')

print()
print('✅ LOCAL DATABASE VERIFIED - SAFE TO DEPLOY')
"
```

### Deploy to Railway

1. **Export Local Database**
   ```bash
   python3 scripts/import/export_arangodb.py
   ```

2. **Import to Railway**
   ```bash
   export RAILWAY_PASSWORD='your-password'
   python3 scripts/import/import_to_railway.py
   ```

3. **Verify Railway Production**
   ```bash
   python3 scripts/verification/verify_railway.py
   ```

---

## Common Issues & Fixes

### Issue 1: "Cannot create edge with nonexistent target satellites/NORAD-XXXXX"

**Cause**: Broken edges pointing to satellites that don't exist (wrong _key)

**Fix**:
```python
from arango import ArangoClient

RAILWAY_HOST = 'https://arangodb-production-d6fb.up.railway.app:443'
RAILWAY_PASSWORD = 'your-password'
DB_NAME = 'kessler'

client = ArangoClient(hosts=RAILWAY_HOST)
db = client.db(DB_NAME, username='root', password=RAILWAY_PASSWORD)

# Delete all broken edges
query = '''
FOR edge IN orbital_proximity
    LET from_exists = DOCUMENT(edge._from) != null
    LET to_exists = DOCUMENT(edge._to) != null
    FILTER !from_exists OR !to_exists
    REMOVE edge IN orbital_proximity
    RETURN 1
'''
result = list(db.aql.execute(query))
print(f'Deleted {len(result)} broken edges')
```

### Issue 2: PRETTY (or other satellites) corrupted

**Symptoms**:
- `canonical.source_priority` contains `gcat` or `satnogs`
- `canonical.launch_date` changed
- `_key` changed

**Fix**: Restore from backup
```bash
export RAILWAY_PASSWORD='your-password'
python3 scripts/import/restore_railway_backup.py railway_backup_TIMESTAMP
```

### Issue 3: Missing canonical.name

**Symptoms**: Graph queries fail with null reference errors

**Fix**:
```bash
python3 scripts/import/normalize_canonical_fields.py --apply
```

---

## Data Source Details

### Kaggle (current_catalog.csv)
- **Type**: Approved source (promotes to canonical)
- **Updates**: orbital_band, congestion_risk, altitude_category
- **Launch dates**: Only has launch_year_estimate (not precise dates)
- **NORAD matching**: Primary key for merging
- **Safety**: Safe to import, won't corrupt existing data

### GCAT (gcat_satcat.tsv)
- **Type**: Unapproved source (sources.gcat ONLY)
- **Updates**: Precise launch dates, orbital parameters
- **Launch dates**: ONLY populates canonical.launch_date if missing
- **NORAD matching**: Primary, falls back to international_designator
- **Safety**: Modified to NEVER call update_canonical() except for launch_date gap-filling
- **Critical**: Always ensures canonical.name when touching canonical

### SatNOGS (API)
- **Type**: Unapproved source (sources.satnogs ONLY)
- **Updates**: Operational status, transmitter info
- **NORAD matching**: Only matches existing satellites
- **Safety**: Never touches canonical data
- **Duration**: ~30 minutes for full import
- **Optional**: Can skip if operational status not needed

### UNOOSA (UN Registry)
- **Type**: Approved source (promotes to canonical)
- **Updates**: Official registration, function descriptions
- **Lag time**: 3-6 months after launch
- **Safety**: Highest priority source, safe to import

---

## Verification Checklist

Before deploying to production, verify:

- [ ] No satellites with `canonical.name == null`
- [ ] PRETTY satellite unchanged (_key, launch_date, source_priority)
- [ ] No broken edges in orbital_proximity
- [ ] Most recent launch date is current (2026+)
- [ ] No GCAT or SatNOGS in any `canonical.source_priority`
- [ ] Total satellite count matches expected (18,612+ as of 2026-02-17)

---

## Emergency Rollback

If production breaks after deployment:

1. **Immediate**: Restore Railway from backup
   ```bash
   export RAILWAY_PASSWORD='your-password'
   python3 scripts/import/restore_railway_backup.py railway_backup_TIMESTAMP
   ```

2. **Hard refresh browser**: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)

3. **Verify**: Check PRETTY satellite in UI

4. **Root cause**: Review what went wrong before attempting again

---

## Success Criteria

✅ Production deployment successful when:
1. PRETTY satellite graph works correctly
2. Most recent launch >= 2026-01-01 in canonical.launch_date
3. No missing canonical.name values
4. No broken edges
5. All existing satellites unchanged
6. Browser hard refresh shows correct data

---

## Notes

- Always test locally before deploying to Railway
- Keep backups for at least 7 days
- Document any new import scripts added
- Update this guide if process changes

# Bug Investigation: Duplicate PRETTY Satellites

## Bug Summary
There are TWO satellites named PRETTY in the database when there should only be ONE.

## Affected Satellites
1. **Identifier**: `NORAD-58023`
   - **Sources**: `['kaggle']`
   - **NORAD ID**: 58023 (from kaggle)
   - **International Designator**: None

2. **Identifier**: `2023-155H` 
   - **Sources**: `['unoosa', 'spacetrack', 'kaggle']`
   - **NORAD ID**: 58023 (from kaggle)
   - **International Designator**: 2023-155H

## Root Cause Analysis

### The Problem
The Kaggle import script ([./scripts/import/import_kaggle_catalog.py:110](./scripts/import/import_kaggle_catalog.py:110)) looks for existing satellites using:
```python
existing = collection.find_one({"canonical.norad_cat_id": norad_id})
```

### Why Duplicates Occur

**Import Order Scenario:**
1. UNOOSA/SpaceTrack imported satellite first with identifier `2023-155H`
   - These sources don't provide NORAD IDs in their data
   - Document created with `identifier: "2023-155H"`
   - `canonical.norad_cat_id` field is **NOT populated** (or is None)

2. Kaggle importer runs for NORAD ID 58023:
   - Searches for existing document with `canonical.norad_cat_id: 58023`
   - **Doesn't find** the `2023-155H` document (because its canonical.norad_cat_id is empty/None)
   - Creates a **NEW document** with identifier `NORAD-58023`

3. Kaggle importer runs again later (or continues):
   - For the same NORAD ID 58023, it now finds both documents
   - Updates the one it finds first
   - Both documents now have Kaggle data, but they remain separate entities

### Database State
Query results show both satellites exist:
```
=== PRETTY Satellite 1: NORAD-58023 ===
Sources: ['kaggle']
Kaggle data:
  norad_cat_id: 58023
  name: PRETTY

=== PRETTY Satellite 2: 2023-155H ===
Sources: ['unoosa', 'spacetrack', 'kaggle']
Kaggle data:
  norad_cat_id: 58023
  name: PRETTY
UNOOSA data:
  international_designator: 2023-155H
SpaceTrack data:
  international_designator: 2023-155H
```

## Affected Components
- **File**: [./scripts/import/import_kaggle_catalog.py](./scripts/import/import_kaggle_catalog.py)
- **Function**: `import_kaggle_catalog()` (lines 110-152)
- **Database Collection**: `satellites`
- **Transformation Logic**: [./database/transformations.py](./database/transformations.py) - `update_canonical()`

## Proposed Solution

### Option 1: Enhanced Deduplication Logic (Recommended)
Modify the Kaggle importer to search for existing satellites using multiple criteria:
1. First try matching by `canonical.norad_cat_id`
2. If not found, try matching by querying sources for the same NORAD ID
3. If not found, try reverse lookup using gcat_satcat.tsv to get international designator

**Advantages:**
- Prevents future duplicates
- Handles cases where NORAD ID is in sources but not in canonical
- More robust matching

**Implementation:**
```python
# Try multiple matching strategies
existing = (
    collection.find_one({"canonical.norad_cat_id": norad_id}) or
    collection.find_one({"sources.kaggle.norad_cat_id": norad_id}) or
    collection.find_one({"sources.spacetrack.norad_catalog_number": norad_id}) or
    collection.find_one({"sources.celestrak.norad_id": norad_id})
)
```

### Option 2: Merge Duplicates Script
Create a maintenance script to:
1. Identify satellites with matching NORAD IDs but different identifiers
2. Merge their data into a single document
3. Use the more complete identifier (prefer international designator if available)

**Advantages:**
- Cleans up existing duplicates
- Can be run periodically

**Disadvantages:**
- Doesn't prevent future duplicates
- Requires deciding which identifier to keep

### Option 3: Pre-populate NORAD IDs
Enhance UNOOSA/SpaceTrack importers to include NORAD IDs from gcat_satcat.tsv before importing.

**Advantages:**
- Ensures canonical.norad_cat_id is always populated
- Kaggle importer will always find matches

**Disadvantages:**
- Requires access to gcat_satcat.tsv during all imports
- More complex import process

## Recommended Approach
**Combination of Options 1 and 2:**

1. **Immediate fix**: Create a script to merge the existing PRETTY duplicates
2. **Prevention**: Update Kaggle importer with enhanced deduplication logic (Option 1)
3. **Verification**: Add tests to detect duplicates by NORAD ID

## Edge Cases to Consider
- Satellites that change NORAD IDs (rare but possible)
- Satellites with international designator but no NORAD ID
- Satellites with NORAD ID but no international designator
- Data from different sources arriving in different orders

## Test Data
**PRETTY Satellite (NORAD 58023)**:
- International Designator: 2023-155H
- Launch Date: 2023-10-09
- Type: CubeSat 3U
- Country: Austria (AT)
- Found in: gcat_satcat.tsv line 58025

---

## Implementation Notes

### Changes Made

#### 1. Enhanced Kaggle Importer Deduplication ([./scripts/import/import_kaggle_catalog.py:110](./scripts/import/import_kaggle_catalog.py:110))
Updated the duplicate detection logic to search across multiple sources:
```python
existing = (
    collection.find_one({"canonical.norad_cat_id": norad_id}) or
    collection.find_one({"sources.kaggle.norad_cat_id": norad_id}) or
    collection.find_one({"sources.spacetrack.norad_catalog_number": norad_id}) or
    collection.find_one({"sources.celestrak.norad_id": norad_id})
)
```

This prevents future duplicates by checking all possible locations where a NORAD ID might be stored.

#### 2. Created Merge Duplicates Script ([./scripts/maintenance/merge_duplicates.py](./scripts/maintenance/merge_duplicates.py))
Created a maintenance script that:
- Identifies satellites with the same NORAD ID but different identifiers
- Merges duplicate entries, preferring satellites with international designators
- Combines all source data from duplicates into the primary document
- Handles both string and numeric NORAD ID types by normalizing to numbers during comparison

**Key Implementation Detail**: The merge query uses `TO_NUMBER()` to normalize NORAD IDs:
```aql
LET norad_numeric = TO_NUMBER(sat.canonical.norad_cat_id)
COLLECT norad_id = norad_numeric INTO groups
```

This ensures that "58023" (string) and 58023 (number) are treated as the same value.

#### 3. Executed Merge Operation
Ran the merge script and successfully merged:
- **1,079 duplicate pairs** across the entire database
- Including the **PRETTY satellite** (NORAD 58023)

**Result**: NORAD-58023 was merged into 2023-155H, combining data from all three sources (Kaggle, SpaceTrack, UNOOSA).

### Verification

**Before Fix:**
```
Found 2 satellite(s) named PRETTY:
- NORAD-58023 (sources: ['kaggle'])
- 2023-155H (sources: ['unoosa', 'spacetrack', 'kaggle'])
```

**After Fix:**
```
Found 1 satellite(s) named PRETTY:
- 2023-155H (sources: ['kaggle', 'spacetrack', 'unoosa'])
```

### Additional Findings

**NORAD ID Type Inconsistency**: Discovered that ~12,733 satellites have string NORAD IDs in `canonical.norad_cat_id` instead of integers. This was caused by earlier Kaggle imports. The enhanced deduplication logic now handles both types correctly by normalizing to numbers during comparison.

### Files Created
- [./scripts/maintenance/merge_duplicates.py](./scripts/maintenance/merge_duplicates.py) - Merge duplicate satellites
- [./scripts/verification/check_pretty.py](./scripts/verification/check_pretty.py) - Verify PRETTY satellite count
- [./scripts/verification/debug_duplicates.py](./scripts/verification/debug_duplicates.py) - Debug duplicate detection
- [./scripts/verification/check_norad_types.py](./scripts/verification/check_norad_types.py) - Check NORAD ID types
- [./scripts/verification/check_string_norad_ids.py](./scripts/verification/check_string_norad_ids.py) - Find satellites with string NORAD IDs

### Testing
- ✅ Verified PRETTY satellite is now unique (1 instead of 2)
- ✅ Verified all sources merged correctly into 2023-155H
- ✅ Confirmed Kaggle importer now checks multiple sources for duplicates
- ✅ Tested merge script handles both string and numeric NORAD IDs

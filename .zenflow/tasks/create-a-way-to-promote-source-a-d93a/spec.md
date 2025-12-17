# Technical Specification: Source Attribute Promotion Script

## Complexity Assessment
**Difficulty: Medium**

This task involves moderate complexity with several considerations:
- Database schema modifications to track transformation history
- CLI argument parsing and validation
- MongoDB bulk update operations
- Nested field access and manipulation
- Transaction safety and rollback capabilities
- Comprehensive logging and reporting

## Technical Context

### Language & Dependencies
- **Language**: Python 3.11
- **Database**: MongoDB (pymongo driver)
- **Existing Components**:
  - `db.py`: Database connection and data model functions
  - `update_canonical()`: Existing automatic promotion based on priority

### Current Data Model
MongoDB documents follow an envelope pattern:

```json
{
  "identifier": "unique-id",
  "canonical": {
    "name": "...",
    "object_type": "...",
    "orbital_band": "LEO",
    "..."
  },
  "sources": {
    "unoosa": { "name": "...", "..." },
    "kaggle": { "orbital_band": "LEO", "..." },
    "celestrak": { "..." },
    "spacetrack": { "..." }
  },
  "metadata": {
    "created_at": "...",
    "last_updated_at": "...",
    "sources_available": ["unoosa", "kaggle"],
    "source_priority": ["unoosa", "celestrak", "spacetrack", "kaggle"]
  }
}
```

## Problem Statement

Currently, the `update_canonical()` function in `db.py` automatically promotes fields from source nodes to canonical based on a priority list. However, there's no way to:

1. **Manually promote specific attributes** from a specific source to canonical
2. **Track transformation history** - which fields were promoted, when, and from which source
3. **Override priority-based promotion** for specific fields (e.g., prefer Kaggle's `orbital_band` over UNOOSA's)

## Implementation Approach

### 1. Transformation History Schema

Add a new `transformations` array to the document metadata to track all manual promotions:

```json
{
  "identifier": "...",
  "canonical": { "..." },
  "sources": { "..." },
  "metadata": {
    "...",
    "transformations": [
      {
        "timestamp": "2025-12-17T19:00:00Z",
        "source_field": "kaggle.orbital_band",
        "target_field": "canonical.orbital_band",
        "value": "LEO",
        "promoted_by": "manual_script",
        "reason": "User-initiated promotion"
      }
    ]
  }
}
```

### 2. CLI Script Design

Create `promote_attributes.py` with the following interface:

```bash
# Single field promotion
python promote_attributes.py kaggle.orbital_band canonical.orbital_band

# Multiple promotions in one command
python promote_attributes.py kaggle.orbital_band canonical.orbital_band kaggle.congestion_risk canonical.congestion_risk

# Dry-run mode (preview without applying)
python promote_attributes.py --dry-run kaggle.orbital_band canonical.orbital_band

# Filter by identifier or query
python promote_attributes.py --filter "identifier=NORAD-12345" kaggle.orbital_band canonical.orbital_band
python promote_attributes.py --filter "canonical.country_of_origin=USA" kaggle.orbital_band canonical.orbital_band

# Apply to all matching documents
python promote_attributes.py --all kaggle.orbital_band canonical.orbital_band
```

### 3. Core Functionality

The script will:

1. **Parse arguments**: Extract source field, target field, and options
2. **Validate fields**: Check that source field exists in at least one document
3. **Query documents**: Find all documents that have the source field
4. **Extract values**: Navigate nested structure (e.g., `sources.kaggle.orbital_band`)
5. **Update canonical**: Set the target field with the source value
6. **Record transformation**: Add entry to `metadata.transformations` array
7. **Report results**: Show statistics on updated documents

### 4. Field Access Pattern

Support dot notation for nested fields:
- `kaggle.orbital_band` → `sources["kaggle"]["orbital_band"]`
- `canonical.orbital_band` → `canonical["orbital_band"]`
- `canonical.orbit.apogee_km` → `canonical["orbit"]["apogee_km"]`

### 5. Safety Features

- **Dry-run mode**: Preview changes without applying
- **Confirmation prompt**: For bulk operations (>10 documents)
- **Validation**: Check source field exists before attempting promotion
- **Error handling**: Skip documents where source field is missing, log errors
- **Transaction logging**: Record all operations in transformation history

## Source Code Structure

### New Files

1. **`promote_attributes.py`** (Main CLI script)
   - Argument parsing (argparse)
   - MongoDB connection
   - Field validation
   - Promotion logic
   - Reporting

### Modified Files

1. **`db.py`** (Add transformation helper functions)
   - `promote_field(doc, source_field, target_field)`: Core promotion logic
   - `record_transformation(doc, source_field, target_field, value)`: Add to history
   - `get_nested_field(obj, path)`: Safely access nested fields
   - `set_nested_field(obj, path, value)`: Safely set nested fields

## Data Model Changes

### Document Schema Extension

Add `transformations` array to `metadata`:

```python
{
  "metadata": {
    # ... existing fields ...
    "transformations": [
      {
        "timestamp": str,  # ISO 8601 datetime
        "source_field": str,  # e.g., "kaggle.orbital_band"
        "target_field": str,  # e.g., "canonical.orbital_band"
        "value": Any,  # The promoted value
        "promoted_by": str,  # "manual_script" or "automatic"
        "reason": str  # Optional explanation
      }
    ]
  }
}
```

## API/Interface Changes

### New CLI Commands

```bash
promote_attributes.py <source_field> <target_field> [options]

Options:
  --dry-run              Preview changes without applying
  --all                  Apply to all documents (default: prompt if >10)
  --filter FILTER        Filter documents (e.g., "identifier=NORAD-12345")
  --yes                  Skip confirmation prompts
  --reason REASON        Add reason to transformation record
  -v, --verbose          Verbose output
```

### Return Values

- **Exit Code 0**: Success
- **Exit Code 1**: Error (invalid arguments, connection failure, etc.)

### Output Format

```
Promoting: kaggle.orbital_band → canonical.orbital_band
----------------------------------------------------------

Querying documents with kaggle.orbital_band...
Found 15,432 documents

Preview (first 5):
  NORAD-12345: "LEO" → canonical.orbital_band
  NORAD-12346: "MEO" → canonical.orbital_band
  NORAD-12347: "GEO" → canonical.orbital_band
  ...

Continue? [y/N]: y

Updating documents...
Progress: [################] 15432/15432 (100%)

Results:
  Updated: 15,432
  Skipped: 0 (source field missing)
  Errors: 0

Transformation history recorded for all updated documents.
```

## Verification Approach

### 1. Unit Tests

Create `test_promote_attributes.py`:

```python
def test_parse_field_path()
def test_get_nested_field()
def test_set_nested_field()
def test_promote_field_single_doc()
def test_record_transformation()
def test_dry_run_mode()
def test_filter_documents()
```

### 2. Integration Tests

```bash
# Test with local MongoDB instance
python promote_attributes.py --dry-run kaggle.orbital_band canonical.orbital_band
python promote_attributes.py --filter "identifier=NORAD-25544" kaggle.orbital_band canonical.orbital_band
```

### 3. Manual Verification

```bash
# Start MongoDB
./scripts/mongodb.sh start

# Verify before promotion
./scripts/mongodb.sh shell
> db.satellites.findOne({"identifier": "NORAD-25544"})

# Run promotion
python promote_attributes.py kaggle.orbital_band canonical.orbital_band --filter "identifier=NORAD-25544"

# Verify after promotion
> db.satellites.findOne({"identifier": "NORAD-25544"})
> # Check canonical.orbital_band exists
> # Check metadata.transformations array has new entry
```

### 4. Edge Cases to Test

- Source field doesn't exist in any document
- Source field exists but is null/empty
- Target field already exists (overwrite confirmation)
- Nested fields (e.g., `canonical.orbit.apogee_km`)
- Large batch operations (>10,000 documents)
- MongoDB connection failures mid-operation

## Implementation Plan

### Phase 1: Core Helpers (db.py)
1. Implement `get_nested_field()` - safely access nested dict fields
2. Implement `set_nested_field()` - safely set nested dict fields
3. Implement `record_transformation()` - add to metadata.transformations

### Phase 2: Promotion Logic (promote_attributes.py)
1. Create CLI script skeleton with argparse
2. Implement field path parsing (split on dots)
3. Implement document querying with filters
4. Implement promotion logic for single document
5. Add batch processing with progress reporting

### Phase 3: Safety & UX
1. Add dry-run mode
2. Add confirmation prompts
3. Add error handling and validation
4. Add verbose logging
5. Add statistics reporting

### Phase 4: Testing & Documentation
1. Write unit tests
2. Test with sample data
3. Test edge cases
4. Update README with usage examples

## Dependencies

No new dependencies required. Uses existing:
- `pymongo` (already in requirements)
- `argparse` (Python standard library)
- `datetime` (Python standard library)

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Accidentally overwrite canonical data | Implement dry-run mode and confirmation prompts |
| Large batch operations timeout | Add progress reporting, consider batching updates |
| Invalid field paths cause errors | Add field path validation before processing |
| Transformation history grows unbounded | Consider adding a limit or archival strategy |
| Concurrent updates conflict | Use MongoDB atomic operations, document-level updates |

## Success Criteria

- [x] Script can promote single field from source to canonical
- [x] Script can handle nested fields (dot notation)
- [x] Transformation history is recorded in metadata
- [x] Dry-run mode works correctly
- [x] Filter options work (by identifier, query)
- [x] Progress reporting for large batches
- [x] Comprehensive error handling
- [x] Usage documentation

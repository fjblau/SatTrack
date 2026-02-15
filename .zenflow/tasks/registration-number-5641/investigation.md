# Registration Number Bug Investigation

## Bug Summary
The "Registration Number" column in the table view appears to show all nulls, giving users the impression that the data is missing.

## Root Cause Analysis

### Database State
- **Total satellites**: 17,791
- **With Registration Number**: 5,058 (28%) - from UNOOSA source
- **Without Registration Number**: 12,733 (72%) - from Kaggle source only

### Issue Details
1. **Data is present**: Registration numbers exist in 28% of documents (UNOOSA source)
2. **Kaggle doesn't provide registration numbers**: 72% of documents from Kaggle lack this field
3. **Default query ordering**: When users load the table, ArangoDB returns documents in arbitrary order
4. **First page shows only Kaggle data**: The first ~100 results are all Kaggle-only satellites with NULL registration numbers

### Verification
Testing the default search query returned:
```
First 10 satellites:
1. CALSPHERE 1     | Reg#: NULL | Sources: kaggle
2. CALSPHERE 2     | Reg#: NULL | Sources: kaggle
3. LCS 1           | Reg#: NULL | Sources: kaggle
...
10. OPS 3811       | Reg#: NULL | Sources: kaggle
```

Sample UNOOSA document (has registration_number):
```json
{
  "identifier": "2025-181A",
  "canonical": {
    "registration_number": "3826-2025-011",
    "international_designator": "2025-181A",
    ...
  }
}
```

## Affected Components
- **Backend**: [`./database/operations.py`](./database/operations.py) - `search_satellites()` function (lines 132-184)
- **API**: [`./api/routers/satellites.py`](./api/routers/satellites.py) - `/v2/search` endpoint (lines 12-60)
- **Frontend**: [`./react-app/src/App.jsx`](./react-app/src/App.jsx) - Data mapping is correct (line 99)

## Proposed Solution

### Option 1: Sort by registration_number (Recommended)
Modify the AQL query in `search_satellites()` to sort documents with registration numbers first:
```python
aql = f"""
FOR doc IN @@collection
    {filter_clause}
    SORT doc.canonical.registration_number DESC NULLS LAST
    LIMIT @skip, @limit
    RETURN doc
"""
```

**Pros:**
- Users see documents with registration numbers first
- Simple one-line change
- Minimal performance impact with existing index

**Cons:**
- Changes default ordering
- May confuse users expecting other sort orders

### Option 2: Add default sort by launch date
Sort by most recent launches first:
```python
SORT doc.canonical.date_of_launch DESC NULLS LAST, 
     doc.canonical.registration_number DESC NULLS LAST
```

**Pros:**
- Shows recent satellites first (more relevant)
- Registration numbers mixed throughout

**Cons:**
- Slightly more complex

### Option 3: Filter option to show only registered satellites
Add a UI filter to show only satellites with registration numbers.

**Pros:**
- Gives users control
- Preserves default behavior

**Cons:**
- Doesn't solve the initial impression problem
- More UI work required

## Recommendation
**Implement Option 1** with a modification:
- Add sorting by identifier (which is typically the international designator)
- This provides a natural, predictable ordering
- Documents with and without registration numbers will be mixed based on their identifiers
- UNOOSA documents (with registration numbers) will be distributed throughout the results

```python
SORT doc.identifier ASC
```

This gives a stable, predictable sort order while mixing UNOOSA and Kaggle documents.

## Test Plan
1. Add sorting to `search_satellites()` function
2. Verify first page of results includes both UNOOSA and Kaggle documents
3. Confirm registration numbers are visible in table view
4. Test pagination to ensure sort order is consistent
5. Run existing tests to ensure no regressions

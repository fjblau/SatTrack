# Import Data from Other Instance - Report

## Summary
Successfully imported the satellite collection from MongoDB instance on port 27018 to the instance on port 27019.

## Actions Taken

1. **Created import script** (`import_from_27018.py`):
   - Connects to source MongoDB on port 27018
   - Connects to target MongoDB on port 27019
   - Reads all documents from `kessler.satellites` collection
   - Imports documents to target instance (removing `_id` to avoid conflicts)

2. **Started target MongoDB instance**:
   - Used docker-compose to start MongoDB container on port 27019
   - Container name: `sattrack`

3. **Executed import**:
   - Successfully imported 18,870 documents
   - Verified both instances have identical document counts

## Result
- Source (port 27018): 18,870 documents
- Target (port 27019): 18,870 documents
- Import: ✓ Complete

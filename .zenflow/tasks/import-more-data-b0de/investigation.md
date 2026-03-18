# Investigation

## Summary

Import 449 records from `58023_PRETTY.json` into the `observations` collection of the `kessler` ArangoDB database, skipping the 2 records already loaded.

## Findings

- **JSON file**: `/Users/frankblau/Downloads/KESTREL_Proxy_JSON_ArangoDB/58023_PRETTY.json`
- **Total records**: 451
- **Already loaded**: 2 records — records[0] and records[1] with epochs:
  - `2026-03-01T00:38:20Z` (key: `2931283`)
  - `2026-03-01T00:48:51Z` (key: `2931285`)
- **Records to import**: 449 (records[2:] — index 2 through 450)
- **Target DB**: `kessler`
- **Target collection**: `observations`
- **Document structure**: JSON fields map directly to ArangoDB document fields, no transformation needed. No `_key` required (auto-generated).

## Proposed Solution

Use the ArangoDB REST API to batch-insert the 449 remaining records:
- Endpoint: `POST /_db/kessler/_api/document/observations`
- Auth: basic auth with root credentials
- Body: JSON array of the 449 records (records[2:])
- Use `?onDuplicate=ignore` or filter by epoch to avoid re-inserting duplicates

### Script approach (Python)

```python
import json, requests

with open('/Users/frankblau/Downloads/KESTREL_Proxy_JSON_ArangoDB/58023_PRETTY.json') as f:
    data = json.load(f)

records_to_import = data[2:]  # skip first 2 already loaded

already_loaded = {
    "2026-03-01T00:38:20Z",
    "2026-03-01T00:48:51Z"
}

# Double-check filter
records_to_import = [r for r in data if r['observation_epoch'] not in already_loaded]

url = "https://arangodb-production-d6fb.up.railway.app:443/_db/kessler/_api/document/observations"
auth = ("root", "bE!tEEblbl2lt!btelllllll!tetl!2eebl2ll!22btblE!EeeEeEtblll!lel2E")

resp = requests.post(url, json=records_to_import, auth=auth)
print(resp.status_code, resp.json())
```

ArangoDB accepts arrays in the document API and returns an array of results.

# Technical Specification: Enrich Script Bug Fix

## Difficulty
**Easy** — A straightforward Python import/binding bug with a clear, minimal fix.

---

## Technical Context

- **Language**: Python 3.11
- **Database**: ArangoDB via `python-arango`
- **Module**: `database/` package with submodules

---

## Root Cause

In `database/__init__.py`, `db` is imported at module load time:

```python
from database.connection import (
    ...
    db,   # binds database.db = None at import time
    ...
)
```

This creates a **snapshot binding** — `database.db` points to `None` (the object that `database.connection.db` referenced at import time).

When `connect_arangodb()` runs later, it does `global client, db, satellites_collection` inside `database/connection.py`, updating `database.connection.db` to the live ArangoDB handle. But `database.db` in the package namespace is **never updated** — it stays `None`.

Scripts that call `db_module.connect_mongodb()` then `db = db_module.db` (e.g., `enrich_launch_data.py`) assign `None` to `db`, causing:

```
AttributeError: 'NoneType' object has no attribute 'aql'
```

### Affected Scripts (all share the same `db = db_module.db` pattern)

| File | Line |
|---|---|
| `scripts/maintenance/enrich_launch_data.py` | 117 |
| `scripts/maintenance/promote_kaggle_orbital.py` | 81 |
| `scripts/maintenance/promote_launch_site.py` | 23 |

---

## Implementation Approach

Fix at the **root cause** in `database/connection.py`. After a successful connection, update the package-level `db` and `satellites_collection` names in `sys.modules['database']` so all importers see the live objects regardless of how they imported them.

```python
import sys

def connect_arangodb():
    global client, db, satellites_collection
    try:
        ...
        db = client.db(DB_NAME, ...)
        satellites_collection = ...
        
        # Sync package-level aliases so `database.db` reflects the live handle
        pkg = sys.modules.get('database')
        if pkg is not None:
            pkg.db = db
            pkg.satellites_collection = satellites_collection
        
        return True
```

This is a standard Python pattern (`sys.modules` mutation) that avoids circular imports, requires no changes to calling scripts, and fixes all three affected scripts at once.

---

## Source Code Changes

| File | Change |
|---|---|
| `database/connection.py` | After successful connection, set `sys.modules['database'].db` and `sys.modules['database'].satellites_collection` |

No other files need modification.

---

## Data Model / API / Interface Changes

None. The fix is internal to the connection module; all public interfaces remain unchanged.

---

## Verification Approach

1. Run `enrich_launch_data.py --dry-run` and confirm it proceeds past "Step 1: Analyze Current Coverage" without `AttributeError`.
2. Optionally run `promote_kaggle_orbital.py --dry-run` and `promote_launch_site.py --dry-run` to verify those scripts are also unaffected.
3. If a linter is configured, run it: `ruff check database/connection.py` (or equivalent).
4. Manual inspection: after `connect_arangodb()` returns, assert `database.db is not None`.

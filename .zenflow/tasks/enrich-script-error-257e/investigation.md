# Bug Investigation: Enrich Script Error

## Bug Summary
`scripts/maintenance/enrich_launch_data.py` fails with:
```
ModuleNotFoundError: No module named 'database'
```
when run from `/app/scripts/maintenance/` (i.e., not from the project root).

## Root Cause Analysis
The script attempts `import database as db_module` on **line 15**, but the `sys.path.insert` that adds the project root to the Python path is on **lines 17–20** — **after** the import. Python resolves imports in execution order, so when line 15 is reached, the `database` package directory is not yet on `sys.path`.

```python
# Lines 12–20 of enrich_launch_data.py (BROKEN order)
import sys
from datetime import datetime, timezone
from collections import defaultdict
import database as db_module   # <-- line 15: fails, path not set yet

from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # <-- line 20: too late
```

The same ordering bug exists in `scripts/maintenance/promote_launch_site.py` (same pattern on lines 7–12).

## Affected Components
- `scripts/maintenance/enrich_launch_data.py` (primary, reported)
- `scripts/maintenance/promote_launch_site.py` (same pattern, also broken)

## Reference: Correct Pattern
Other scripts in the same directory fix this correctly by doing `sys.path.insert` **before** any project-local imports. Examples:
- `scripts/maintenance/merge_duplicates.py`
- `scripts/maintenance/precompute_graph_metrics.py`

## Proposed Solution
In both affected scripts, move the `sys.path.insert` call (and its `from pathlib import Path`) to **before** `import database as db_module`:

```python
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime, timezone
from collections import defaultdict
import database as db_module
```

This is a minimal, safe change. No logic is modified — only import ordering.

## Edge Cases / Side Effects
- No logic changes; purely import-order fix.
- The `database` package is a real directory at the project root with `__init__.py`, so the fix will work correctly once the path is set before import.
- No tests need to be modified; existing test suite covers `database` module usage.

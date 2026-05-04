# Spec 1 Migration Guide — `satellites` → `objects`

Run this guide after deploying the Spec 1 build to Vercel/Railway. All migration scripts connect to the ArangoDB instance via `ARANGO_HOST`, `ARANGO_USER`, and `ARANGO_PASSWORD` environment variables.

---

## Pre-flight checklist

Before running anything:

- [ ] **Back up ArangoDB** — take a snapshot or use `arangodump` before touching production data
- [ ] Confirm the new build is live and the API is responding (`GET /v2/health` or any safe endpoint)
- [ ] Confirm ArangoDB is accessible from the machine you will run scripts on (direct connection or Railway tunnel)
- [ ] Set env vars in your shell:
  ```sh
  export ARANGO_HOST=https://your-arango-host:8529
  export ARANGO_USER=root
  export ARANGO_PASSWORD=your-password
  ```
- [ ] `cd` to the project root so relative `sys.path` inserts work correctly

---

## Migration order

Run scripts **in this exact order**. Each script is idempotent — if it detects the step was already done it will print a message and exit safely.

### Step 1 — Rename `satellites` → `objects`

```sh
python scripts/migration/migrate_collection_rename.py
```

What it does:
- Renames the `satellites` collection to `objects` in-place (no data is copied or deleted)
- Recreates core indexes (`identifier` unique, `canonical.international_designator`, `canonical.registration_number`)
- Creates or updates the `satellite_relationships` named graph to point at `objects`

Expected output (first run):
```
Collection 'satellites' exists: True
Collection 'objects' exists: False
Will rename 'satellites' (26742 documents) → 'objects'
Renamed 'satellites' → 'objects'
Recreating indexes on 'objects'...
Core indexes recreated.
Graph 'satellite_relationships' does not exist. Creating...
Graph 'satellite_relationships' created.
Migration complete.
```

> **If you see** `Collection already renamed to 'objects'. Nothing to do.` — the step was already done. Continue to Step 2.

> **If you see** `ERROR: 'objects' collection already has documents.` — stop and investigate before proceeding.

---

### Step 2 — Create new indexes

```sh
python scripts/migration/migrate_create_new_indexes.py
```

What it does:
- Adds a persistent index on `canonical.object_class` (for `by-class` endpoint performance)
- Adds persistent indexes on `identifier_aliases.norad` and `identifier_aliases.cospar` (for alias lookup)

These indexes are additive and safe to run at any time.

---

### Step 3 — Classify objects (add `canonical.object_class`)

```sh
python scripts/migration/migrate_classify_objects.py
```

What it does:
- Reads each document's `canonical.object_type` and maps it to the new `canonical.object_class` enum
- Writes `canonical.object_class` onto every document
- Records a transformation log entry in `metadata.transformations` per document
- **Does not modify or remove** `canonical.object_type` (kept as deprecated field)

Mapping applied (ALL CAPS production values included):

| `object_type` | → `object_class` |
|---|---|
| `PAYLOAD`, `PAY`, `Payload` | `Payload` |
| `ROCKET BODY`, `R/B`, `Rocket Body` | `Rocket Body` |
| `DEBRIS`, `DEB`, `Debris` | `Unknown` _(refined by Spec 2)_ |
| `UNKNOWN`, `UNK`, `Unknown` | `Unknown` |
| `Mission-Related Object`, `MRO` | `Mission-Related Object` |
| anything else | `Unknown` |

You will be shown a distribution preview and prompted to confirm before any writes are made. Type `y` to proceed.

Expected confirmation prompt:
```
=== Classify objects (add canonical.object_class) ===

Total documents: 26,742

Current object_type distribution:
  PAYLOAD                       :   18,431  →  Payload
  DEBRIS                        :    5,210  →  Unknown
  ROCKET BODY                   :    2,891  →  Rocket Body
  UNKNOWN                       :      210  →  Unknown

Classify all 26,742 documents? (y/N):
```

---

### Step 4 — Backfill `identifier_aliases`

```sh
python scripts/migration/migrate_backfill_aliases.py
```

What it does:
- Adds the top-level `identifier_aliases` field to every document
- Backfills `identifier_aliases.norad` from `canonical.norad_cat_id`
- Backfills `identifier_aliases.cospar` from `canonical.international_designator`
- Idempotent — skips documents that already have both keys set

You will be shown a count of documents that need backfilling and prompted to confirm.

---

### Step 5 — Rebuild AQL/RAG context

```sh
python scripts/migration/migrate_rebuild_aql_rag.py
```

What it does:
- Validates that `_SCHEMA_CONTEXT_BASE` in `api/services/aql_agent_service.py` no longer references `satellites` (confirms the code deploy succeeded)
- Rebuilds the ChromaDB vector index used by the `/v2/ask` general assistant

This script is safe to re-run. If ChromaDB is not configured (no `CHROMA_*` env vars), the index rebuild step will be skipped with a warning — the AQL schema validation still passes.

---

### Step 6 — Verify

```sh
python scripts/migration/migrate_verify_object_model.py
```

Runs a series of read-only checks and prints `[OK]`, `[WARN]`, or `[FAIL]` for each:

| Check | Pass condition |
|---|---|
| `objects` collection exists | collection present, document count > 0 |
| `satellites` collection gone | absent or empty |
| `object_class` coverage | ≥ 90% of documents have the field set |
| `identifier_aliases` coverage | ≥ 90% of documents have the field set |
| `satellite_relationships` graph | points at `objects`, not `satellites` |

A clean run looks like:
```
[OK] Collection 'objects' exists: 26,742 documents
[OK] Old 'satellites' collection does not exist
[OK] object_class coverage: 26,742/26,742 (100.0%)
[OK] identifier_aliases coverage: 26,742/26,742 (100.0%)
[OK] Graph 'satellite_relationships' points at 'objects'

--- Summary ---
All checks passed.
```

Exit code 0 = success, 1 = at least one failure.

---

## Post-migration smoke test

After all six steps pass, hit the new API endpoints to confirm the application is working end-to-end:

```sh
BASE=https://your-api-host

# New objects endpoint
curl "$BASE/v2/objects/25544"

# Object class filter
curl "$BASE/v2/objects/by-class/Payload?limit=5"

# Alias lookup
curl "$BASE/v2/objects/by-alias/norad/25544"

# Object classes enum (new endpoint)
curl "$BASE/v2/object-classes"

# Backward-compat satellite endpoint still works
curl "$BASE/v2/satellite/25544"

# Stats
curl "$BASE/v2/objects/stats"
```

All six should return 200 with valid JSON bodies.

---

## Rollback

Spec 1 **cannot be rolled back automatically** once Step 1 (collection rename) has been committed. The rename is irreversible without a restore from backup.

If you need to revert:
1. Restore from the pre-migration ArangoDB backup
2. Roll back the Railway/Vercel deployment to the previous build
3. The previous build still references `satellites` — it will work against the restored backup

Steps 2–6 are individually reversible:
- **Step 2** (indexes): drop the three new indexes via ArangoDB web UI or `arangosh`
- **Step 3** (object_class): the field can be removed with an AQL `UPDATE doc WITH {canonical: UNSET(doc.canonical, "object_class")} IN objects` sweep
- **Step 4** (identifier_aliases): similarly removable via AQL
- **Steps 5–6**: read-only or code-level only, no DB changes

---

## Environment variable reference

| Variable | Default | Notes |
|---|---|---|
| `ARANGO_HOST` | `http://localhost:8529` | Full URL including protocol and port |
| `ARANGO_USER` | `root` | |
| `ARANGO_PASSWORD` | `kessler_dev_password` | Override in production |

All six scripts read these from the environment or `.env` file (via `python-dotenv` if installed).

---

## Decisions carried into this migration

Per the locked spec decisions:

- `/v2/satellite/*` endpoints are **preserved** and will be removed in Spec 3
- `canonical.object_type` is **preserved** (deprecated) and will be removed in a follow-on cleanup PR after Spec 1 is validated
- The `satellite_relationships` named graph keeps its name
- `DEBRIS` → `Unknown` in `object_class` (will be refined by Spec 2's DISCOS promote step)

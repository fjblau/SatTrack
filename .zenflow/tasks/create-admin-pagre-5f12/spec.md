# Technical Specification: Admin Page

## Difficulty Assessment
**Medium** — Requires a new React component, a new FastAPI router, and background script execution with status polling. No complex architectural changes, but care is needed around subprocess management and output streaming.

---

## Technical Context

### Language & Dependencies
- **Frontend**: React 19, JSX, plain CSS modules (no additional libraries needed)
- **Backend**: Python, FastAPI, standard library `subprocess` and `asyncio`
- **No new npm or pip packages required**

### Existing Patterns to Follow
- **Frontend tabs**: `activeTab` state in `App.jsx` drives nav; each tab renders a `<div>` conditionally. New `admin` tab follows the same pattern.
- **API routers**: FastAPI `APIRouter` under `api/routers/`, registered in `api/main.py`. New `admin.py` router follows the same structure.
- **CSS**: Each component has a paired `.css` file imported directly. New `AdminPage.css` mirrors `App.css` analytics section patterns.

---

## Implementation Approach

### Overview
1. Add an **Admin** nav button to the right of **Analytics** in `App.jsx`.
2. Create a new `AdminPage` React component that lists runnable data enrichment scripts grouped by category, each with a **Run** button, live status indicator, and scrollable log output.
3. Add a new FastAPI `admin` router with endpoints to list available scripts, trigger execution, and poll run status.
4. Script runs are executed in-process via Python `subprocess` on the server; run state (status + stdout/stderr) is kept in a server-side in-memory dict keyed by a UUID run ID.

### Script Catalogue
The admin router will expose a hardcoded catalogue of enrichment scripts drawn from:
- `scripts/maintenance/` (enrichment / data promotion)
- `scripts/population/` (graph edge population)

Each entry contains: `id`, `name`, `description`, `path` (relative to project root), `category`.

Verification and import scripts are excluded from the UI to avoid accidental destructive imports.

---

## Source Code Changes

### New Files
| File | Purpose |
|---|---|
| `react-app/src/components/AdminPage.jsx` | Admin page React component |
| `react-app/src/components/AdminPage.css` | Styles for AdminPage |
| `api/routers/admin.py` | FastAPI router for script management |

### Modified Files
| File | Change |
|---|---|
| `react-app/src/App.jsx` | Import `AdminPage`, add `admin` tab button and render block |
| `api/main.py` | Import and register `admin` router |

---

## API Changes

### New Router: `api/routers/admin.py`
Prefix: `/v2/admin`

#### `GET /v2/admin/scripts`
Returns the catalogue of available scripts.

**Response:**
```json
{
  "scripts": [
    {
      "id": "enrich_launch_data",
      "name": "Enrich Launch Data",
      "description": "Enriches satellite documents with launch dates and country data",
      "category": "maintenance"
    }
  ]
}
```

#### `POST /v2/admin/scripts/{script_id}/run`
Triggers the script asynchronously (via `subprocess.Popen`). Returns a run ID immediately.

**Response:**
```json
{ "run_id": "<uuid>" }
```

#### `GET /v2/admin/runs/{run_id}`
Polls run status and accumulated output.

**Response:**
```json
{
  "run_id": "<uuid>",
  "script_id": "enrich_launch_data",
  "status": "running" | "success" | "error",
  "output": "...stdout+stderr...",
  "started_at": "2026-03-08T12:00:00Z",
  "finished_at": null | "2026-03-08T12:05:00Z"
}
```

### Server-Side State
A module-level dict `_runs: dict[str, RunRecord]` stores run state. Each `RunRecord` holds the `Popen` object reference (while running), accumulated output string, status, and timestamps. Output is read from the subprocess stdout+stderr (combined via `stderr=subprocess.STDOUT`) when the status endpoint is polled.

---

## Frontend Component: `AdminPage.jsx`

### UI Structure
```
AdminPage
├── Header: "Data Enrichment Scripts"
├── Category sections (maintenance, population)
│   └── ScriptCard (per script)
│       ├── Script name + description
│       ├── Run button (disabled while running)
│       ├── Status badge (idle / running / success / error)
│       └── Log output area (scrollable, monospace, shown after run)
```

### Behaviour
- On **Run** click: `POST /v2/admin/scripts/{id}/run` → store `run_id` in component state.
- Poll `GET /v2/admin/runs/{run_id}` every 2 seconds while `status === 'running'`.
- Stop polling when `status` is `success` or `error`.
- Display accumulated output in a scrollable `<pre>` block.
- Only one run per script at a time (button disabled while running).

---

## Verification Approach

### Lint / Type Check
```bash
# Frontend
cd react-app && npm run build

# Backend (if lint configured)
cd .. && python -m py_compile api/routers/admin.py
```

### Manual Verification
1. Start both services (`./start.sh`)
2. Open browser, confirm **Admin** tab appears to the right of **Analytics**
3. Click **Admin** tab — script list loads grouped by category
4. Click **Run** on a maintenance script — status changes to `running`, log output appears
5. Wait for completion — status becomes `success` or `error`, final output shown

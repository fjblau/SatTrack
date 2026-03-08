# Technical Specification: Admin Page is Blank

## Difficulty
**Easy** — trivial bug fix; wrong URL path in a fetch call.

## Root Cause
`AdminPage.jsx` makes three fetch calls using the `/api/v2/admin/...` path prefix, but the backend router registers routes under `/v2/admin/...`.

The Vite dev-server proxy is configured without a path rewrite rule for `/api`, so a request to `/api/v2/admin/scripts` is forwarded verbatim to `http://127.0.0.1:8000/api/v2/admin/scripts`, which does not exist on the backend. The backend returns a 404 (or network error), the catch block silently swallows it, `scripts` stays `[]`, and nothing renders below the "Data Enrichment Scripts" heading.

All other API calls in the project use `/v2/...` directly (consistent with the `/v2` proxy entry in `vite.config.js` and the backend router prefixes).

## Technical Context
- **Language**: JavaScript/JSX (React 19)
- **File to modify**: `react-app/src/components/AdminPage.jsx`
- **No backend changes needed**

## Implementation Approach
Replace the three incorrect fetch paths in `AdminPage.jsx`:

| Current (broken) | Fixed |
|---|---|
| `/api/v2/admin/scripts` | `/v2/admin/scripts` |
| `/api/v2/admin/scripts/${scriptId}/run` | `/v2/admin/scripts/${scriptId}/run` |
| `/api/v2/admin/runs/${runId}` | `/v2/admin/runs/${runId}` |

## Files Modified
- `react-app/src/components/AdminPage.jsx` — fix three fetch URLs

## API / Interface Changes
None. The backend API already has the correct routes.

## Verification
1. Start the backend and frontend (`./start.sh`)
2. Navigate to the Admin tab — the script list should render with grouped categories (maintenance, population)
3. Confirm the `/v2/admin/scripts` network request returns HTTP 200 with a `scripts` array

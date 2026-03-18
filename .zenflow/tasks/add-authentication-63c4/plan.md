# Full SDD workflow

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Agent Instructions

---

## Workflow Steps

### [x] Step: Requirements
<!-- chat-id: 02d054f6-bc57-4929-9f74-f299857cab00 -->

Create a Product Requirements Document (PRD) based on the feature description.

1. Review existing codebase to understand current architecture and patterns
2. Analyze the feature definition and identify unclear aspects
3. Ask the user for clarifications on aspects that significantly impact scope or user experience
4. Make reasonable decisions for minor details based on context and conventions
5. If user can't clarify, make a decision, state the assumption, and continue

Focus on **what** the feature should do and **why**, not **how** it should be built. Do not include technical implementation details, technology choices, or code-level decisions — those belong in the Technical Specification.

Save the PRD to `{@artifacts_path}/requirements.md`.

### [x] Step: Technical Specification
<!-- chat-id: 293f4cd0-7397-4cac-b335-78e468bc18ee -->

Create a technical specification based on the PRD in `{@artifacts_path}/requirements.md`.

1. Review existing codebase architecture and identify reusable components
2. Define the implementation approach

Do not include implementation steps, phases, or task breakdowns — those belong in the Planning step.

Save to `{@artifacts_path}/spec.md` with:
- Technical context (language, dependencies)
- Implementation approach referencing existing code patterns
- Source code structure changes
- Data model / API / interface changes
- Verification approach using project lint/test commands

### [x] Step: Planning
<!-- chat-id: 17ee07ae-bd00-4901-917d-55e4c0861f46 -->

Detailed implementation plan created. Steps below replace the generic Implementation step.

### [x] Step: Backend auth router and config
<!-- chat-id: 0a7c9529-f98e-432a-9663-10e523ab4428 -->

Implement backend authentication foundation:

- Add `AuthConfig` class to `config.py` reading `APP_USERNAME` (default `"admin"`) and `APP_PASSWORD` (no default; log startup warning if empty) from env
- Create `api/routers/auth.py` with:
  - In-memory token store: module-level `set[str]`
  - `POST /v2/auth/login`: validate `{username, password}` against `AuthConfig`; on success generate `secrets.token_urlsafe(32)`, add to store, return `{"token": "..."}` ; on failure return HTTP 401 `{"detail": "Invalid credentials"}`
  - `POST /v2/auth/logout`: remove token from store, return `{"detail": "Logged out"}`
- Register `auth` router in `api/main.py`
- Update `.env.example` to document `APP_USERNAME` and `APP_PASSWORD`
- Write unit tests in `tests/unit/test_auth_router.py` covering: successful login, wrong password, logout invalidates token

### [x] Step: Backend auth middleware
<!-- chat-id: 2201bdf7-eeca-4fe2-bd28-4e44e2946034 -->

Implement `api/middleware/auth.py` containing a Starlette middleware class that:

- Allows `POST /v2/auth/login` through without checking a token
- For all other requests: reads `Authorization: Bearer <token>` header; if token is absent or not in the in-memory store, returns HTTP 401 JSON immediately
- Register the middleware in `api/main.py` (added **after** CORS middleware so CORS headers are present on 401 responses)
- Write unit/integration tests in `tests/unit/test_auth_middleware.py` covering: unauthenticated request → 401, authenticated request → passes through, login endpoint bypassed

### [x] Step: Frontend apiFetch utility and LoginPage component
<!-- chat-id: 2de3ccf7-44a1-4c4a-b93a-577110fd8e51 -->

- Create `react-app/src/utils/apiFetch.js`: wraps `fetch`, reads token from `sessionStorage`, injects `Authorization: Bearer` header; on 401 response clears `sessionStorage` and dispatches `"auth:expired"` window event; re-exports the same interface as `fetch` so callsites need minimal change
- Create `react-app/src/components/LoginPage.jsx`: form with username + password fields; `POST /v2/auth/login`; on success calls `onLogin(token)` prop; on failure shows error message
- Create `react-app/src/components/LoginPage.css`: basic centered card styles consistent with existing `.app-header` / component styles

### [x] Step: Wire auth into App.jsx and replace fetch in all components
<!-- chat-id: 1e0b6f0a-4ae8-4422-b84e-e32ef7c2c83c -->

- Modify `react-app/src/App.jsx`:
  - Add `token` state initialised from `sessionStorage.getItem("auth_token")`
  - When `token` is falsy render only `<LoginPage onLogin={...} />`; otherwise render full app
  - Add Logout button to `<header class="app-header">`: calls `POST /v2/auth/logout` via `apiFetch`, clears `sessionStorage`, sets `token` to `null`
  - Listen to `"auth:expired"` window event and reset `token` to `null`
  - Replace all bare `fetch(` calls in `App.jsx` with `apiFetch(`
- Replace `fetch(` with `apiFetch(` in all 17 component files that currently use it:
  `OrbitCalculationModal`, `SatelliteNeighborhood`, `DetailPanel`, `GraphExplorer`, `GraphViewer`, `MqttConfigModal`, `PathFinderPanel`, `RegistrationDocumentAnalytics`, `CentralityView`, `AdminPage`, `ObservationsModal`, `CollisionRiskView`, `EvolutionTimelineView`, `TimelineChart`, `ConstellationBrowser`, `ObservationsView`, `FunctionAnalytics`
- Add `import apiFetch from '../utils/apiFetch'` (or relative path as appropriate) to each modified file

### [x] Step: Verification
<!-- chat-id: b3bca599-125f-4cd9-b033-121034d1169d -->

Run all checks and record results:

- `cd react-app && npm run build` — must succeed with no errors
- `python -m pytest tests/` — all tests pass
- Manual smoke test per spec verification steps 1–10

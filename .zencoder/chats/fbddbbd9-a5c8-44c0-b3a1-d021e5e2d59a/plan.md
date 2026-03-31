# Spec and build

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:

- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

---

## Workflow Steps

### [x] Step: Technical Specification

Assess the task's difficulty, as underestimating it leads to poor outcomes.

- easy: Straightforward implementation, trivial bug fix or feature
- medium: Moderate complexity, some edge cases or caveats to consider
- hard: Complex logic, many caveats, architectural considerations, or high-risk changes

Create a technical specification for the task that is appropriate for the complexity level:

- Review the existing codebase architecture and identify reusable components.
- Define the implementation approach based on established patterns in the project.
- Identify all source code files that will be created or modified.
- Define any necessary data model, API, or interface changes.
- Describe verification steps using the project's test and lint commands.

Save the output to `/Users/frankblau/SatTrack/.zencoder/chats/fbddbbd9-a5c8-44c0-b3a1-d021e5e2d59a/spec.md` with:

- Technical context (language, dependencies)
- Implementation approach
- Source code structure changes
- Data model / API / interface changes
- Verification approach

If the task is complex enough, create a detailed implementation plan based on `/Users/frankblau/SatTrack/.zencoder/chats/fbddbbd9-a5c8-44c0-b3a1-d021e5e2d59a/spec.md`:

- Break down the work into concrete tasks (incrementable, testable milestones)
- Each task should reference relevant contracts and include verification steps
- Replace the Implementation step below with the planned tasks

Rule of thumb for step size: each step should represent a coherent unit of work (e.g., implement a component, add an API endpoint, write tests for a module). Avoid steps that are too granular (single function).

Save to `/Users/frankblau/SatTrack/.zencoder/chats/fbddbbd9-a5c8-44c0-b3a1-d021e5e2d59a/plan.md`. If the feature is trivial and doesn't warrant this breakdown, keep the Implementation step below as is.

**Stop here.** Present the specification (and plan, if created) to the user and wait for their confirmation before proceeding.

---

### [x] Step: Backend Analytics & AQL Endpoints
Implement new analytics endpoints and the AQL execution route in `api/routers/observations.py`.
- Implement `GET /v2/observations/analytics/health-over-time`.
- Implement `GET /v2/observations/analytics/anomaly-distribution`.
- Implement `GET /v2/observations/analytics/source-distribution`.
- Implement `POST /v2/observations/aql`.
- **Verification**: Run `curl` commands to verify each endpoint returns correct data.

### [x] Step: Frontend Configuration & Navigation
Update constants and navigation to include the new Observation Graphs page.
- Add new endpoints to `react-app/src/config/constants.js`.
- Modify `react-app/src/App.jsx` to add "Observation Graphs" tab (admin-only).
- **Verification**: Login as admin and verify the new button appears in the header.

### [x] Step: ObservationGraphs Component Implementation
Create the `ObservationGraphs` component with sidebar and visualization views.
- Create `react-app/src/components/ObservationGraphs.jsx`.
- Create `react-app/src/components/ObservationGraphs.css`.
- Implement "Health Trends" visualization (SVG-based).
- Implement "Anomaly Analysis" visualization.
- Implement "Source Statistics" visualization.
- **Verification**: Click through different views in the sidebar and verify charts render correctly.

### [x] Step: AQL Editor Implementation
Add the AQL editor functionality to the `ObservationGraphs` component.
- Implement the AQL editor UI in `ObservationGraphs.jsx`.
- Implement query execution and results rendering.
- **Verification**: Execute valid and invalid AQL queries and verify results/error messages.

### [x] Step: Final Review & Testing
Perform final manual verification and run tests/linters.
- Verify admin-only access (login as demo user).
- Run `npm run lint` and backend tests.
- Write a report to `/Users/frankblau/SatTrack/.zencoder/chats/fbddbbd9-a5c8-44c0-b3a1-d021e5e2d59a/report.md`.

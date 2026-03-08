# Spec and build

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:
- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

If you are blocked and need user clarification, mark the current step with `[!]` in plan.md before stopping.

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 75167f7a-691b-4936-abb0-acc5247ee4b6 -->

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

Save the output to `{@artifacts_path}/spec.md` with:
- Technical context (language, dependencies)
- Implementation approach
- Source code structure changes
- Data model / API / interface changes
- Verification approach

If the task is complex enough, create a detailed implementation plan based on `{@artifacts_path}/spec.md`:
- Break down the work into concrete tasks (incrementable, testable milestones)
- Each task should reference relevant contracts and include verification steps
- Replace the Implementation step below with the planned tasks

Rule of thumb for step size: each step should represent a coherent unit of work (e.g., implement a component, add an API endpoint, write tests for a module). Avoid steps that are too granular (single function).

Important: unit tests must be part of each implementation task, not separate tasks. Each task should implement the code and its tests together, if relevant.

Save to `{@artifacts_path}/plan.md`. If the feature is trivial and doesn't warrant this breakdown, keep the Implementation step below as is.

---

### [x] Step: Implement backend admin router
<!-- chat-id: b88a2335-499d-4a5e-bcb4-f31206561eb0 -->

Create `api/routers/admin.py` with:
- Script catalogue (maintenance + population scripts with id, name, description, category, path)
- `GET /v2/admin/scripts` — returns catalogue
- `POST /v2/admin/scripts/{script_id}/run` — spawns subprocess via `subprocess.Popen`, stores run state in module-level dict, returns run_id (UUID)
- `GET /v2/admin/runs/{run_id}` — reads accumulated stdout/stderr from Popen, returns status + output

Register the router in `api/main.py`.

Verify: `python -m py_compile api/routers/admin.py`

### [ ] Step: Implement AdminPage frontend component

Create `react-app/src/components/AdminPage.jsx` and `AdminPage.css`:
- Fetch and display script catalogue grouped by category on mount
- Per-script card: name, description, Run button, status badge, scrollable log `<pre>`
- On Run: POST to trigger, store run_id, poll every 2 s until status is success/error
- Disable Run button while a run is in progress for that script

Update `react-app/src/App.jsx`:
- Import `AdminPage`
- Add `admin` tab button to the right of Analytics in `<nav>`
- Add conditional render block for `activeTab === 'admin'`

Verify: `cd react-app && npm run build`

### [ ] Step: Integration verification and report

1. Start both services and manually verify:
   - Admin tab appears to the right of Analytics
   - Script list renders grouped by category
   - Run button triggers execution, log output appears and updates
   - Status badge transitions correctly (idle → running → success/error)
2. Write `{@artifacts_path}/report.md` describing what was implemented, how it was tested, and any issues encountered.

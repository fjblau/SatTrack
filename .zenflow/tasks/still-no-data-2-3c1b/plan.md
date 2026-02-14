# Fix bug

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Workflow Steps

### [x] Step: Investigation and Planning
<!-- chat-id: 249aaf3e-244b-456d-b8c3-99a5799415c8 -->

Analyze the bug report and design a solution.

1. Review the bug description, error messages, and logs
2. Clarify reproduction steps with the user if unclear
3. Check existing tests for clues about expected behavior
4. Locate relevant code sections and identify root cause
5. Propose a fix based on the investigation
6. Consider edge cases and potential side effects

Save findings to `{@artifacts_path}/investigation.md` with:
- Bug summary
- Root cause analysis
- Affected components
- Proposed solution

### [x] Step: Implementation
<!-- chat-id: 59835b75-19ee-49c4-9144-66acc94c14c9 -->
Read `{@artifacts_path}/investigation.md`
Implement the bug fix.

1. Add/adjust regression test(s) that fail before the fix and pass after
2. Implement the fix
3. Run relevant tests
4. Update `{@artifacts_path}/investigation.md` with implementation notes and test results

**Implementation Completed**:
- Created `/v2/graphs/satellite/{id}/neighborhood` endpoint
- Fixed SatelliteNeighborhood component (search endpoint & response mapping)
- Fixed ConstellationBrowser component (removed invalid depth parameter)
- Fixed Cytoscape node_size console warnings
- Fixed database connection bugs in collision_service.py, lineage_service.py, graph_operations.py
- Fixed populate_collision_risks.py script (status filter, field names, database connection)
- Populated production database with 191,000 collision risk edges
- Fixed collision risk score display precision (2→4 decimal places)
- All changes committed and pushed to main branch
- Verified production deployment with collision risk data showing correctly

If blocked or uncertain, ask the user for direction.

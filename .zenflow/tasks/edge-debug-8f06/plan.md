# Fix bug

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Workflow Steps

### [x] Step: Investigation and Planning
<!-- chat-id: 47400fd5-df9f-49e7-83ad-b6d7e030cd8b -->

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
<!-- chat-id: 9b647266-0c31-479a-9caf-934167fbad86 -->
Read `{@artifacts_path}/investigation.md`
Implement the bug fix.

1. Add/adjust regression test(s) that fail before the fix and pass after
2. Implement the fix
3. Run relevant tests
4. Update `{@artifacts_path}/investigation.md` with implementation notes and test results

If blocked or uncertain, ask the user for direction.

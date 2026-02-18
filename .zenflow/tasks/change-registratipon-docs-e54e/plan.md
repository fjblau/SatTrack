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

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 600ef6f6-3d5a-441c-a899-d419d4d8ff5c -->

**Completed**: Created detailed technical specification in `spec.md`

**Difficulty Assessment**: Medium complexity
- Multiple file modifications across frontend and backend
- New API endpoint and React component creation
- Follows established patterns in the codebase

---

### [x] Step: Create Backend API Endpoint
<!-- chat-id: b0ca44ed-dc66-439c-85cf-c2343af7219a -->

Create the new API endpoint for registration documents analytics in the backend.

**Tasks**:
- Add new `/v2/graphs/registration-documents-analytics` endpoint to `api/routers/graphs.py`
- Implement AQL query to fetch all registration documents with filtering and sorting
- Calculate summary statistics (total docs, total satellites, average, top country)
- Support query parameters: `sort_by`, `sort_order`, `search`
- Return complete response structure as defined in spec

**Verification**:
- Test endpoint manually: `curl http://localhost:8000/v2/graphs/registration-documents-analytics`
- Test with parameters: sorting, searching
- Verify response structure matches spec
- Check for any Python linting errors

---

### [ ] Step: Create Registration Documents Analytics Component

Create the new React component for displaying registration documents analytics.

**Tasks**:
- Create `react-app/src/components/RegistrationDocumentAnalytics.jsx`
- Create `react-app/src/components/RegistrationDocumentAnalytics.css`
- Implement data fetching from new API endpoint
- Build summary statistics cards (total docs, satellites, averages)
- Create sortable table with columns: URL, Satellite Count, Countries, Created At
- Add search/filter functionality for URLs
- Handle loading and error states
- Style following patterns from FunctionAnalytics component

**Verification**:
- Component renders without errors
- Table displays data correctly
- Sorting works on all columns
- Search filters results
- Statistics calculate correctly
- Run frontend lint if available

---

### [ ] Step: Remove Registration Docs from Graphs Tab

Remove the registration documents graph visualization from the GraphExplorer component.

**Tasks**:
- Remove "Registration Docs" button from graph type selector in `GraphExplorer.jsx`
- Remove registration document selector section
- Remove `documents`, `selectedDocument` states and related logic
- Clean up any unused imports
- Check `GraphViewer.jsx` and remove registration graph rendering logic
- Remove `selectedDocument` prop from GraphViewer

**Verification**:
- Graphs tab displays without errors
- No "Registration Docs" button visible
- Other graph types still work correctly
- No console warnings about unused variables
- Run frontend lint if available

---

### [ ] Step: Integrate New Tab in Main App

Add the new Registration Docs tab to the main application navigation.

**Tasks**:
- Import `RegistrationDocumentAnalytics` component in `App.jsx`
- Add API endpoint constant to `config/constants.js`
- Add "Registration Docs" tab button to navigation
- Add conditional rendering for the new tab
- Position as 5th tab after Analytics

**Verification**:
- New tab appears in navigation
- Clicking tab displays the analytics page
- Navigation between all tabs works correctly
- No console errors
- Run frontend lint if available

---

### [ ] Step: Final Testing and Documentation

Perform comprehensive testing and create completion report.

**Tasks**:
- Start full application with `./start.sh`
- Test all tabs to ensure nothing broke
- Test the new Registration Docs analytics page thoroughly
- Test sorting, filtering, statistics display
- Check for console errors in browser
- Verify API endpoint works correctly
- Test edge cases (empty search, large result sets)
- Write completion report to `.zenflow/tasks/change-registratipon-docs-e54e/report.md`

**Verification**:
- All functionality works as specified
- No console errors or warnings
- Manual testing complete
- Report documents implementation and any issues encountered

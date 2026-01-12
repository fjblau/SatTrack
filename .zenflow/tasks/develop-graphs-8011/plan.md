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
<!-- chat-id: ded50d7a-b928-4109-b781-8039a4f7768c -->

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

Save to `{@artifacts_path}/plan.md`. If the feature is trivial and doesn't warrant this breakdown, keep the Implementation step below as is.

---

### [x] Step: Phase 1 - Foundation: Database Graph Structure
<!-- chat-id: CURRENT -->

Create ArangoDB graph collections and infrastructure:
1. ✓ Create edge collections: `constellation_membership`, `registration_links`, `orbital_proximity`
2. ✓ Create `registration_documents` document collection
3. ✓ Define named graph `satellite_relationships` in ArangoDB
4. ✓ Update `db.py` with graph management functions
5. ✓ Create migration script `migrate_graph_structure.py`

**Verification**:
- ✓ Run migration script successfully
- ✓ Verify edge collections exist in ArangoDB (3 edge collections, 0 edges currently)
- ✓ Verify graph definition is created
- ✓ Run basic AQL graph traversal queries

**Created Files**:
- `db.py`: Added graph constants and 10 graph management functions
- `migrate_graph_structure.py`: Migration script for creating graph structure
- `verify_graph_structure.py`: Verification script for testing graph setup

---

### [ ] Step: Phase 1 - Foundation: Build Registration Document Network

Populate registration document graph:
1. Extract unique registration documents from satellite data
2. Create document nodes in `registration_documents` collection
3. Build edges linking satellites to registration documents
4. Add indexes on edge collections

**Verification**:
- Verify all registration documents are extracted
- Check edge count matches satellite count
- Query registration document with satellites (AQL traversal)
- Test performance of graph queries

---

### [ ] Step: Phase 1 - Foundation: Build Constellation Membership Graph

Create constellation network edges:
1. Extract constellation data from `sources.kaggle.satellite_constellation`
2. Build `constellation_membership` edges
3. Create helper functions for constellation queries

**Verification**:
- Verify Glonass, OneWeb, and Other constellations have edges
- Test constellation member retrieval queries
- Verify edge counts per constellation

---

### [ ] Step: Phase 1 - Foundation: Basic Graph API Endpoints

Create initial FastAPI endpoints for graphs:
1. `GET /api/graphs/constellation/{name}` - Get constellation members
2. `GET /api/graphs/registration-document/{doc_id}` - Get satellites by registration doc
3. `GET /api/graphs/stats` - Get overall graph statistics
4. Implement standard graph response format (nodes + edges JSON)

**Verification**:
- Test all endpoints with curl/Postman
- Verify response format matches spec
- Test with various constellation names
- Check API documentation at `/docs`

---

### [ ] Step: Phase 1 - Foundation: React Graph Viewer Component

Create basic graph visualization:
1. Install `cytoscape` and related packages in react-app
2. Create `GraphViewer.jsx` component with basic Cytoscape integration
3. Create `GraphControls.jsx` for layout selection
4. Create `GraphLegend.jsx` for node/edge type legend
5. Add "Graphs" tab to main navigation

**Verification**:
- Component renders without errors
- Can load sample graph data from API
- Layout controls work (force-directed, circular, etc.)
- Legend displays correctly
- Manual testing in browser

---

### [ ] Step: Phase 2 - Core Analytics: Orbital Proximity Calculation

Implement orbital proximity edge creation:
1. Create `build_orbital_proximity_edges()` function in migration script
2. Implement proximity score calculation (apogee, perigee, inclination similarity)
3. Filter satellites by orbital band for performance
4. Build edges for satellites within proximity thresholds
5. Add `orbital_proximity` edge collection indexes

**Verification**:
- Run proximity calculation on sample dataset
- Verify proximity scores are reasonable
- Check edge count is manageable (<100k)
- Test query performance for proximity graphs
- Validate proximity logic with known satellite pairs

---

### [ ] Step: Phase 2 - Core Analytics: Orbital Proximity API & Visualization

Create orbital proximity graph endpoints and UI:
1. `GET /api/graphs/orbital-proximity` - Get proximity graph with filters
2. Create `OrbitalProximityGraph.jsx` component
3. Add orbital band and congestion risk filters
4. Implement color coding by congestion risk
5. Add node sizing by proximity connection count

**Verification**:
- Test API endpoint with various filters
- Verify graph visualizes congestion hotspots
- Test interactive features (click node to highlight connections)
- Performance test with large subgraphs
- Manual testing in browser

---

### [ ] Step: Phase 2 - Core Analytics: Launch Timeline Graph

Create temporal launch sequence graph:
1. Build `launch_sequence` edges based on launch dates
2. Create `GET /api/graphs/launch-timeline` endpoint with date filters
3. Create `LaunchTimeline.jsx` component
4. Implement timeline layout (hierarchical or chronological)
5. Add date range filters and country filters

**Verification**:
- Verify temporal edges link satellites chronologically
- Test API with various date ranges
- Visualize deployment campaigns clearly
- Test filtering by country
- Manual testing with known launch sequences

---

### [ ] Step: Phase 3 - Advanced Features: Function Similarity Network

Implement function similarity graph:
1. Create function classification/categorization logic
2. Build `function_similarity` edges based on keyword matching
3. Create `GET /api/graphs/function-similarity/{satellite_id}` endpoint
4. Implement similarity score calculation
5. Add UI component for exploring similar satellites

**Verification**:
- Test function classification accuracy
- Verify similarity edges make semantic sense
- Test API endpoint with various satellites
- Visualize function clusters
- Manual testing of similarity results

---

### [ ] Step: Phase 3 - Advanced Features: Country Relations Graph

Create country-level aggregation graph:
1. Aggregate satellites by country
2. Calculate shared orbital band statistics
3. Build `country_space_relations` edges
4. Create `GET /api/graphs/country/{name}` endpoint
5. Create `CountryRelationsGraph.jsx` component with country-level view

**Verification**:
- Verify country aggregation is accurate
- Test country relationship calculations
- Visualize geopolitical patterns
- Test with major space-faring nations
- Manual testing and validation

---

### [ ] Step: Final - Testing, Documentation & Polish

Finalize implementation with tests and documentation:
1. Write unit tests for graph query functions (`test_graph_db.py`)
2. Write API integration tests (`test_graph_api.py`)
3. Add React component tests for graph viewers
4. Performance benchmarking and optimization
5. Write completion report to `{@artifacts_path}/report.md`

**Verification**:
- All tests pass: `pytest test_graph_*.py`
- Frontend tests pass: `cd react-app && npm run test`
- API documentation is complete
- Performance meets success metrics (<2s queries, 60fps rendering)
- Report documents implementation, testing, and challenges

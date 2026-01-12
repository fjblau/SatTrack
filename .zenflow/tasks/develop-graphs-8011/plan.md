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

### [x] Step: Phase 1 - Foundation: Build Registration Document Network

Populate registration document graph:
1. ✓ Extract unique registration documents from satellite data (746 unique docs)
2. ✓ Create document nodes in `registration_documents` collection (745 created)
3. ✓ Build edges linking satellites to registration documents (5,054 edges)
4. ✓ Add indexes on edge collections (auto edge indexes verified)

**Verification**:
- ✓ Verify all registration documents are extracted (746 unique, 5,055 satellites)
- ✓ Check edge count matches satellite count (5,054 edges created)
- ✓ Query registration document with satellites (AQL traversal working)
- ✓ Test performance of graph queries (graph and edge traversals working)

**Created Files**:
- `analyze_registration_docs.py`: Analyzed registration document data
- `populate_registration_network.py`: Created registration documents and edges
- `add_graph_indexes.py`: Verified edge collection indexes
- `verify_registration_network.py`: Comprehensive verification with 5 test cases (all passed)

---

### [x] Step: Phase 1 - Foundation: Build Constellation Membership Graph

Create constellation network edges:
1. ✓ Extract constellation data from `sources.kaggle.satellite_constellation` (14,890 satellites, 6 constellations)
2. ✓ Build `constellation_membership` edges (14,884 edges in star topology)
3. ✓ Designated constellation hubs (one per constellation)

**Verification**:
- ✓ Verify Glonass, OneWeb, Starlink Gen 1, and Other constellations have edges
- ✓ Test constellation member retrieval queries (all working via hub traversal)
- ✓ Verify edge counts per constellation:
  - Starlink Gen 1: 9,257 edges (9,258 total satellites)
  - Other: 4,267 edges (4,268 total)
  - OneWeb: 1,207 edges (1,208 total)
  - Beidou: 68 edges (69 total)
  - Glonass: 55 edges (56 total)
  - Galileo: 30 edges (31 total)

**Created Files**:
- `populate_constellation_network.py`: Created star topology with constellation hubs
- `verify_constellation_network.py`: Comprehensive verification with 6 test cases (all passed)

**Network Topology**: Star pattern where all satellites in a constellation connect to a designated hub satellite, enabling efficient O(1) hub lookup and O(n) member traversal

---

### [x] Step: Phase 1 - Foundation: Basic Graph API Endpoints

Create initial FastAPI endpoints for graphs:
1. ✓ `GET /v2/graphs/constellation/{name}` - Get constellation members
2. ✓ `GET /v2/graphs/registration-document/{doc_key}` - Get satellites by registration doc
3. ✓ `GET /v2/graphs/stats` - Get overall graph statistics
4. ✓ Implement standard graph response format (nodes + edges JSON)

**Verification**:
- ✓ Test all endpoints with curl (all working)
- ✓ Verify response format matches spec (standard format: data, timestamp, optional message)
- ✓ Test with various constellation names (Starlink Gen 1, OneWeb, invalid names)
- ✓ Test limit parameter on constellation and registration endpoints
- ✓ Server restarted and serving endpoints at http://127.0.0.1:8000

**Results**:
- All 3 endpoints operational and tested via HTTP
- Proper error handling for invalid inputs
- Graph stats: 19,615 nodes (18,870 satellites + 745 docs), 19,938 edges

---

### [x] Step: Phase 1 - Foundation: React Graph Viewer Component

Create basic graph visualization:
1. ✓ Install `cytoscape` and `cytoscape-cola` packages in react-app (120 packages added)
2. ✓ Create `GraphViewer.jsx` component with Cytoscape integration
3. ✓ Create `GraphExplorer.jsx` for graph type selection and data loading
4. ✓ Integrate layout controls (cola, circle, grid, concentric) directly in GraphViewer
5. ✓ Add inline legend for node/edge types
6. ✓ Add "Graph View" tab to main navigation with tab switcher

**Implementation Details**:
- **GraphViewer.jsx**: Full Cytoscape integration with 4 layouts, fit-to-view, node click handlers
- **GraphExplorer.jsx**: Sidebar with constellation/registration document selection
- **App.jsx**: Tab navigation between Table View and Graph View
- **Styling**: Complete CSS for graph controls, legend, and responsive layout
- **Node Types**: Satellites (blue circles), Hub satellites (red, larger), Registration documents (green rectangles)
- **Edge Styling**: Bezier curves with arrow targets, hover/selection states

**Verification**:
- ✓ Build completed successfully (no errors)
- ✓ Components structure validated
- ✓ API proxy configured in vite.config.js (/v2 → localhost:8000)
- ✓ Ready for manual browser testing

---

### [ ] Step: Phase 2 - Core Analytics: Orbital Proximity Calculation
<!-- chat-id: CURRENT -->

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

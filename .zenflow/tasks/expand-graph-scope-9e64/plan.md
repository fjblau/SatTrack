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

### [x] Step: Phase 1 - Backend Infrastructure
<!-- chat-id: e8f018ef-1c1e-4d7d-85c3-fa041af0f770 -->

Create foundational graph analytics infrastructure and data structures.

**Tasks:**
- Create `database/graph_analytics.py` module for graph algorithms
- Implement helper functions for graph traversal and analysis
- Add new edge collection schemas (collision_risk_edges, satellite_lineage)
- Create population scripts for new edge collections in `scripts/population/`
- Add required database indexes for performance optimization
- Write unit tests for graph analytics utilities

**Verification:**
- Run `pytest tests/unit/test_graph_analytics.py`
- Verify new edge collections exist in ArangoDB
- Confirm indexes are created properly
- Check population scripts can process sample data

**Files Modified/Created:**
- `database/graph_analytics.py` (new)
- `database/connection.py` (add new edge collection constants)
- `scripts/population/populate_collision_risks.py` (new)
- `scripts/population/populate_satellite_lineage.py` (new)
- `tests/unit/test_graph_analytics.py` (new)

---

### [x] Step: Phase 2 - Multi-Hop Path Finding
<!-- chat-id: ec7a863b-baab-4b78-867f-d02273aea4af -->

Implement shortest path and path finding capabilities.

**Tasks:**
- Implement `find_shortest_path()` in graph_analytics module
- Implement `find_all_paths()` with depth limit
- Add API endpoint `GET /v2/graphs/paths/{from_id}/{to_id}`
- Add query parameters: max_depth, edge_types[], algorithm
- Implement caching for path queries
- Write integration tests for path finding endpoint
- Add error handling for invalid satellite IDs

**Verification:**
- Run `pytest tests/integration/test_path_finding.py`
- Test API endpoint with sample satellite pairs
- Verify paths are logical and respect depth limits
- Check cache hit rates for repeated queries

**Files Modified/Created:**
- `database/graph_analytics.py` (add path functions)
- `api/routers/graphs.py` (add path endpoints)
- `tests/integration/test_path_finding.py` (new)

---

### [ ] Step: Phase 3 - Centrality Analysis

Implement network centrality metrics calculation.

**Tasks:**
- Implement degree centrality calculation
- Implement betweenness centrality calculation
- Implement closeness centrality calculation
- Add API endpoint `GET /v2/graphs/analytics/centrality`
- Support metric selection and edge type filtering
- Add caching with 24-hour TTL for centrality results
- Write unit tests for centrality algorithms
- Add integration tests for centrality endpoint

**Verification:**
- Run `pytest tests/unit/test_centrality.py`
- Run `pytest tests/integration/test_centrality_api.py`
- Verify centrality scores are computed correctly
- Test performance with large graph datasets
- Validate cache behavior

**Files Modified/Created:**
- `database/graph_analytics.py` (add centrality functions)
- `api/routers/graphs.py` (add centrality endpoint)
- `tests/unit/test_centrality.py` (new)
- `tests/integration/test_centrality_api.py` (new)

---

### [ ] Step: Phase 4 - Collision Risk Network

Implement collision risk analysis and visualization.

**Tasks:**
- Create collision risk calculation algorithm (based on orbital proximity)
- Populate collision_risk_edges collection
- Add API endpoint `GET /v2/graphs/collision-risks`
- Support filtering by risk_threshold, orbital_band
- Calculate risk scores based on orbital parameters
- Add validation for risk calculations
- Write tests for collision risk logic
- Add integration tests for collision risk endpoint

**Verification:**
- Run `pytest tests/unit/test_collision_risks.py`
- Run `pytest tests/integration/test_collision_api.py`
- Verify risk scores align with orbital mechanics
- Test edge population with sample satellites
- Validate filtering and thresholds

**Files Modified/Created:**
- `api/services/collision_service.py` (new)
- `database/graph_analytics.py` (add collision analysis)
- `api/routers/graphs.py` (add collision endpoint)
- `scripts/population/populate_collision_risks.py` (implement)
- `tests/unit/test_collision_risks.py` (new)
- `tests/integration/test_collision_api.py` (new)

---

### [ ] Step: Phase 5 - Multi-Dimensional Cross-Domain Queries

Implement complex queries combining multiple edge types.

**Tasks:**
- Implement cross-constellation proximity analysis
- Implement country cooperation network query
- Implement function-based clustering query
- Add API endpoints for each cross-domain query type
- Support complex filtering and aggregation
- Optimize multi-edge-type traversals
- Write integration tests for cross-domain endpoints

**Verification:**
- Run `pytest tests/integration/test_cross_domain_queries.py`
- Test each cross-domain endpoint with realistic data
- Verify queries combine edge types correctly
- Check performance of multi-type traversals

**Files Modified/Created:**
- `api/routers/graphs.py` (add 3 cross-domain endpoints)
- `database/graph_analytics.py` (add multi-edge traversal helpers)
- `tests/integration/test_cross_domain_queries.py` (new)

---

### [ ] Step: Phase 6 - Satellite Lineage Tracking

Implement hierarchical satellite family relationships.

**Tasks:**
- Create lineage detection algorithm (name patterns, manufacturers)
- Populate satellite_lineage edge collection
- Add API endpoint `GET /v2/graphs/lineage/{satellite_id}`
- Support ancestor/descendant traversal parameters
- Add generation tracking and metadata
- Write tests for lineage detection
- Add integration tests for lineage endpoint

**Verification:**
- Run `pytest tests/unit/test_lineage_detection.py`
- Run `pytest tests/integration/test_lineage_api.py`
- Verify lineage relationships are logical
- Test with known satellite families (GPS, Iridium, etc.)
- Validate generation tracking

**Files Modified/Created:**
- `api/services/lineage_service.py` (new)
- `database/graph_analytics.py` (add lineage traversal)
- `api/routers/graphs.py` (add lineage endpoint)
- `scripts/population/populate_satellite_lineage.py` (implement)
- `tests/unit/test_lineage_detection.py` (new)
- `tests/integration/test_lineage_api.py` (new)

---

### [ ] Step: Phase 7 - Community Detection

Implement graph clustering and community detection.

**Tasks:**
- Implement connected components algorithm
- Implement label propagation for community detection
- Add API endpoint `GET /v2/graphs/communities`
- Support algorithm selection parameter
- Add minimum community size filtering
- Cache community detection results (12-hour TTL)
- Write tests for community algorithms
- Add integration tests for communities endpoint

**Verification:**
- Run `pytest tests/unit/test_communities.py`
- Run `pytest tests/integration/test_communities_api.py`
- Verify communities are meaningful and non-overlapping
- Test with different algorithms
- Validate cache performance

**Files Modified/Created:**
- `database/graph_analytics.py` (add community algorithms)
- `api/routers/graphs.py` (add communities endpoint)
- `tests/unit/test_communities.py` (new)
- `tests/integration/test_communities_api.py` (new)

---

### [ ] Step: Phase 8 - Frontend Graph Explorer Integration

Integrate new graph types into React frontend.

**Tasks:**
- Add new graph type selectors (Path Finder, Centrality, Collision Risks, etc.)
- Create PathFinderPanel component for interactive path finding
- Create CentralityView component with highlighted hub nodes
- Create CollisionRiskView component with risk color coding
- Update GraphViewer to handle new graph data formats
- Add loading states and error handling
- Style new components consistently
- Test all new graph types in browser

**Verification:**
- Manual testing in browser for all new graph types
- Verify data fetching and rendering
- Check responsive design
- Test error states and loading indicators
- Validate user interactions

**Files Modified/Created:**
- `react-app/src/components/GraphExplorer.jsx` (add new types)
- `react-app/src/components/PathFinderPanel.jsx` (new)
- `react-app/src/components/CentralityView.jsx` (new)
- `react-app/src/components/CollisionRiskView.jsx` (new)
- `react-app/src/components/GraphViewer.jsx` (update rendering)
- `react-app/src/config/constants.js` (add new constants)
- `react-app/src/components/*.css` (styling)

---

### [ ] Step: Phase 9 - Temporal Graph Evolution

Implement time-series graph analysis.

**Tasks:**
- Add temporal filtering to graph queries
- Implement graph evolution timeline endpoint
- Calculate growth metrics (node/edge counts, density)
- Add API endpoint `GET /v2/graphs/evolution/timeline`
- Support date range and granularity parameters
- Create TimelineView frontend component
- Add animated visualization support
- Write integration tests for evolution endpoint

**Verification:**
- Run `pytest tests/integration/test_evolution_api.py`
- Verify timeline data is accurate
- Test animation in frontend
- Check performance with different granularities

**Files Modified/Created:**
- `database/graph_analytics.py` (add temporal analysis)
- `api/routers/graphs.py` (add evolution endpoint)
- `react-app/src/components/TimelineView.jsx` (new)
- `tests/integration/test_evolution_api.py` (new)

---

### [ ] Step: Phase 10 - Graph Recommendations

Implement graph-based recommendation system.

**Tasks:**
- Implement similarity calculation based on graph structure
- Calculate neighbor-based recommendations
- Add API endpoint `GET /v2/graphs/recommendations/{satellite_id}`
- Support different recommendation strategies
- Add collaborative filtering logic
- Write tests for recommendation algorithms
- Add integration tests for recommendations endpoint

**Verification:**
- Run `pytest tests/unit/test_recommendations.py`
- Run `pytest tests/integration/test_recommendations_api.py`
- Verify recommendations are relevant and diverse
- Test with various satellite types
- Validate recommendation scores

**Files Modified/Created:**
- `database/graph_analytics.py` (add recommendation logic)
- `api/routers/graphs.py` (add recommendations endpoint)
- `tests/unit/test_recommendations.py` (new)
- `tests/integration/test_recommendations_api.py` (new)

---

### [ ] Step: Phase 11 - Performance Optimization & Polish

Optimize query performance and add polish.

**Tasks:**
- Profile slow graph queries and optimize AQL
- Tune cache TTLs and sizes
- Add query result pagination
- Implement background job for pre-computing metrics
- Add monitoring and logging for graph operations
- Optimize frontend rendering for large graphs
- Add progressive loading for large datasets
- Run performance benchmarks

**Verification:**
- Benchmark query times for different graph sizes
- Verify cache hit rates >60%
- Test pagination works correctly
- Monitor memory usage under load
- Validate frontend performance with 1000+ nodes

**Files Modified/Created:**
- `api/routers/graphs.py` (optimize queries)
- `api/services/cache_service.py` (tune settings)
- `database/graph_analytics.py` (query optimization)
- `scripts/maintenance/precompute_graph_metrics.py` (new)

---

### [ ] Step: Phase 12 - Documentation & Final Report

Complete documentation and summary report.

**Tasks:**
- Update API documentation with new endpoints
- Create user guide for new graph features
- Document all graph analytics algorithms
- Add code comments and docstrings
- Create examples for each graph query type
- Write comprehensive report to `{@artifacts_path}/report.md`
- Include performance metrics and benchmarks
- Document known limitations and future work

**Verification:**
- Review all documentation for completeness
- Verify code examples work correctly
- Check API docs are accurate
- Validate report covers all implemented features

**Files Modified/Created:**
- `API_DOCUMENTATION.md` (update)
- `DEVELOPER_GUIDE.md` (add graph section)
- `{@artifacts_path}/report.md` (new)
- Various source files (add/improve docstrings)

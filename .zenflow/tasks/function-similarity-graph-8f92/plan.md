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
<!-- chat-id: 7ddd772e-bbcd-431f-91bd-000ac07c5fab -->

**Completed**: Technical specification created at `.zenflow/tasks/function-similarity-graph-8f92/spec.md`

**Difficulty Assessment**: Medium

**Root Cause Identified**: The Function Similarity Graph endpoint tries to show edges between satellites with similar functions, but only includes existing constellation/registration/proximity edges. Since satellites with similar functions often don't share these relationships, the graph has nodes but no edges.

**Solution**: Create synthetic similarity edges between satellites that share the same function category and orbital band (subclustering approach).

---

### [ ] Step: Implement Backend Synthetic Similarity Edges

Modify the `/v2/graphs/function-similarity` endpoint to generate synthetic edges between satellites with matching function categories.

**Files to modify**:
- `./api/routers/graphs.py` (lines 1091-1230, function `get_function_similarity_graph`)

**Implementation details**:
1. After categorizing and limiting satellites, add AQL query logic to generate similarity edges
2. Use subclustering by (function_category, orbital_band) to control edge count
3. Create edges between all pairs within each subcluster
4. Set edge properties:
   - `relationship_type`: `"function_similarity"`
   - `function_category`: shared category name
   - `orbital_band`: shared orbital band
   - `similarity_score`: 1.0
5. Optionally keep existing constellation/registration edges for additional context
6. Update stats to include similarity_edges and existing_edges counts

**Verification**:
- Test endpoint: `curl "http://127.0.0.1:8000/v2/graphs/function-similarity?limit=50"`
- Verify response includes non-empty edges array
- Verify edges have `relationship_type: "function_similarity"`
- Check that edge count is reasonable (500-2000 edges for ~350 satellites)

---

### [ ] Step: Add Frontend Edge Styling for Function Similarity

Update the GraphViewer component to properly style and render function similarity edges with category-specific colors.

**Files to modify**:
- `./react-app/src/components/GraphViewer.jsx` (lines 24-304 for styling, 614-688 for data handling)

**Implementation details**:
1. Add Cytoscape CSS selector for `edge[relationship_type="function_similarity"]`
2. Implement category color mapping function:
   - Communications: Blue (#3498db)
   - Earth Observation: Green (#27ae60)
   - Scientific Research: Purple (#9b59b6)
   - Navigation: Orange (#e67e22)
   - Military-Defense: Red (#c0392b)
   - Space Station: Teal (#16a085)
   - Technology-Testing: Yellow (#f39c12)
   - Other: Gray (#95a5a6)
3. Apply colors to edges via `data(category_color)` or direct color mapping
4. Set appropriate edge width (2px) and opacity (0.6) for visual clarity
5. Ensure edges render in `loadAllFunctionCategories` and `filterFunctionGraph` functions

**Verification**:
- Start application: `./start.sh`
- Navigate to Function Similarity graph in UI
- Verify edges are visible and colored by category
- Test category filtering to ensure edges filter correctly
- Check browser console for rendering errors

---

### [ ] Step: Manual Testing and Verification

Perform end-to-end testing of the Function Similarity Graph feature.

**Test scenarios**:
1. **Initial Load**:
   - Graph displays nodes (satellites)
   - Graph displays edges connecting satellites
   - Edges are clearly visible and colored
   - Stats show non-zero edge count

2. **Category Filtering**:
   - Click individual function categories
   - Verify nodes and edges filter correctly
   - Verify only edges within selected categories are shown
   - Stats update properly

3. **Performance**:
   - Graph renders within 2 seconds
   - Layout algorithm completes smoothly
   - No browser console errors
   - No UI freezing or lag

4. **Visual Quality**:
   - Clear clusters visible for each function category
   - Edge colors distinguish categories effectively
   - Graph is interpretable and useful

**Verification checklist**:
- [ ] Graph shows nodes and edges
- [ ] Edge count > 0 in stats
- [ ] Edges colored by function category
- [ ] Category filtering works
- [ ] Performance is acceptable
- [ ] No console errors

**Report creation**:
- Document findings in `.zenflow/tasks/function-similarity-graph-8f92/report.md`
- Include screenshots if any issues found
- Note any performance observations
- List any edge cases or improvements for future work

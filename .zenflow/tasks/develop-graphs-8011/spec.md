# Technical Specification: Graph Features for Kessler Satellite Database

## Task Complexity Assessment

**Difficulty**: Medium to Hard

**Rationale**:
- Requires understanding of graph database concepts and ArangoDB graph features
- Involves both backend (graph queries, edge collections) and frontend (visualization) work
- Multiple graph patterns with varying complexity
- Potential performance considerations with 18,870+ documents
- Integration with existing data model without disrupting current functionality

## Technical Context

### Current Architecture
- **Database**: ArangoDB (currently using only document collections)
- **Backend**: Python 3.11 with FastAPI
- **Frontend**: React 19.2.3 with Vite 7.2.7
- **Data Volume**: 18,870 satellite documents
- **Data Sources**: UNOOSA, CelesTrak, Space-Track, Kaggle

### Current Data Model

The satellite data is stored in a **document-based envelope pattern**:

```json
{
  "_key": "2025-206B",
  "identifier": "2025-206B",
  "canonical": {
    "name": "(GLONASS)",
    "country_of_origin": "Russian Federation",
    "international_designator": "2025-206B",
    "norad_cat_id": 65590,
    "orbital_band": "MEO",
    "congestion_risk": "MEDIUM",
    "orbit": { "apogee_km": 19166, "perigee_km": 19094, ... },
    "status": "in orbit",
    "function": "...",
    "date_of_launch": "2025-09-13",
    ...
  },
  "sources": {
    "unoosa": { ... },
    "spacetrack": { ... },
    "kaggle": { "satellite_constellation": "Glonass", ... }
  },
  "metadata": { "transformations": [...], ... }
}
```

### Key Data Characteristics
- **Countries**: 39+ unique countries
- **Constellations**: 3 identified (Glonass, OneWeb, Other)
- **Orbital Bands**: 6 types (GEO, HEO, LEO-Equatorial, LEO-Inclined, LEO-Polar, MEO)
- **Functions**: 179+ different satellite functions
- **Status values**: in orbit, recovered, decayed, etc.
- **Congestion Risk levels**: LOW, MEDIUM, HIGH

## Graph Use Cases & Recommendations

### 1. **Constellation Network Graph** (High Value, Medium Complexity)

**Description**: Visualize satellite constellations as connected networks

**Graph Pattern**:
- **Nodes**: Satellites
- **Edges**: `BELONGS_TO_CONSTELLATION`
- **Attributes**: constellation name, size, orbital characteristics

**Value Proposition**:
- Visualize mega-constellations (OneWeb, Glonass)
- Identify constellation fragmentation
- Track constellation deployment progress over time

**Implementation Approach**:
```
CREATE EDGE COLLECTION: constellation_membership
Edge Properties:
  - _from: satellites/{satellite_key}
  - _to: satellites/{satellite_key} (constellation "hub" or shared property)
  - constellation_name: string
  - membership_confidence: float (data source reliability)
```

**Query Example**:
```aql
FOR sat IN satellites
  FILTER sat.sources.kaggle.satellite_constellation == "OneWeb"
  RETURN sat
```

---

### 2. **Orbital Proximity Graph** (High Value, High Complexity)

**Description**: Connect satellites that share similar orbital parameters and may pose collision risks

**Graph Pattern**:
- **Nodes**: Satellites
- **Edges**: `ORBITAL_PROXIMITY`
- **Attributes**: distance estimate, risk level, orbital band overlap

**Value Proposition**:
- Space traffic management visualization
- Collision risk assessment
- Congestion hotspot identification
- Visualize "orbital neighborhoods"

**Implementation Approach**:
```
CREATE EDGE COLLECTION: orbital_proximity
Edge Properties:
  - _from: satellites/{satellite_key}
  - _to: satellites/{satellite_key}
  - orbital_band: string (shared)
  - congestion_risk: string
  - proximity_score: float (calculated from apogee, perigee, inclination similarity)
  - potential_conjunctions: boolean
```

**Proximity Calculation**:
- Satellites in same orbital band
- Similar apogee/perigee (within ±50km)
- Similar inclination (within ±5°)
- Calculate proximity_score based on orbital parameter deltas

**Query Example**:
```aql
FOR sat IN satellites
  FILTER sat.canonical.orbital_band == "LEO-Polar"
  FOR other IN satellites
    FILTER other.canonical.orbital_band == "LEO-Polar"
    FILTER sat._key != other._key
    FILTER ABS(sat.canonical.orbit.perigee_km - other.canonical.orbit.perigee_km) < 50
    FILTER ABS(sat.canonical.orbit.inclination_degrees - other.canonical.orbit.inclination_degrees) < 5
    RETURN {from: sat, to: other, proximity: "HIGH"}
```

---

### 3. **Country Collaboration & Competition Graph** (Medium Value, Medium Complexity)

**Description**: Visualize international relationships through satellite launches and orbital band usage

**Graph Pattern**:
- **Nodes**: Countries (aggregated from satellites)
- **Edges**: `SHARES_ORBITAL_BAND`, `LAUNCHES_SIMILAR_MISSIONS`
- **Attributes**: satellite count, orbital band distribution, function overlap

**Value Proposition**:
- Geopolitical space analysis
- Identify space race dynamics
- International collaboration patterns
- Resource competition in orbital slots (especially GEO)

**Implementation Approach**:
```
CREATE EDGE COLLECTION: country_space_relations
Edge Properties:
  - _from: countries/{country_key}
  - _to: countries/{country_key}
  - shared_orbital_bands: array[string]
  - satellite_count_A: int
  - satellite_count_B: int
  - relation_type: "competition" | "collaboration" | "neutral"
```

**Aggregation needed**:
- Create virtual "country" nodes from satellite data
- Calculate shared orbital space
- Identify function overlaps

---

### 4. **Temporal Launch Sequence Graph** (Medium Value, Low-Medium Complexity)

**Description**: Timeline-based graph showing launch sequences and satellite deployment patterns

**Graph Pattern**:
- **Nodes**: Satellites
- **Edges**: `LAUNCHED_BEFORE`, `SAME_LAUNCH_EVENT`
- **Attributes**: launch date, launch vehicle, place of launch

**Value Proposition**:
- Track deployment campaigns
- Identify launch vehicle reliability patterns
- Visualize space race timeline
- Analyze launch frequency trends

**Implementation Approach**:
```
CREATE EDGE COLLECTION: launch_sequence
Edge Properties:
  - _from: satellites/{earlier_satellite}
  - _to: satellites/{later_satellite}
  - time_delta_days: int
  - same_country: boolean
  - same_launch_vehicle: boolean (if available)
```

**Query Example**:
```aql
FOR sat IN satellites
  FILTER sat.canonical.date_of_launch >= "2024-01-01"
  SORT sat.canonical.date_of_launch ASC
  RETURN {
    date: sat.canonical.date_of_launch,
    name: sat.canonical.name,
    country: sat.canonical.country_of_origin
  }
```

---

### 5. **Function Similarity Network** (Medium Value, Medium Complexity)

**Description**: Connect satellites with similar or complementary functions

**Graph Pattern**:
- **Nodes**: Satellites
- **Edges**: `SIMILAR_FUNCTION`, `COMPLEMENTARY_FUNCTION`
- **Attributes**: function categories, mission overlap

**Value Proposition**:
- Identify redundant capabilities
- Find capability gaps
- Mission type clustering
- Technology diffusion tracking

**Implementation Approach**:
```
CREATE EDGE COLLECTION: function_similarity
Edge Properties:
  - _from: satellites/{satellite_key}
  - _to: satellites/{satellite_key}
  - similarity_score: float
  - function_category: string (extracted/classified)
  - mission_type: string
```

**Function Categorization** (NLP/keyword-based):
- Communications
- Earth observation/remote sensing
- Navigation (GNSS)
- Scientific research
- Military/defense
- Technology demonstration

---

### 6. **Registration Document Network** (Low-Medium Value, Low Complexity)

**Description**: Group satellites by their UN registration documents

**Graph Pattern**:
- **Nodes**: Satellites, Registration Documents
- **Edges**: `REGISTERED_IN`
- **Attributes**: registration number, document path, registration date

**Value Proposition**:
- Track batch registrations
- Identify administrative patterns
- Link related satellites from same operator
- Document coverage analysis

**Implementation Approach**:
```
CREATE EDGE COLLECTION: registration_links
CREATE NODE COLLECTION: registration_documents

Edge Properties:
  - _from: satellites/{satellite_key}
  - _to: documents/{document_key}
  - registration_date: string
  - registration_number: string
```

---

## Recommended Implementation Priority

### Phase 1: Foundation (High Priority, Low Hanging Fruit)
1. **Registration Document Network** (simplest, immediate value)
2. **Constellation Network** (high visibility, moderate complexity)

### Phase 2: Core Analytics (High Priority, Higher Complexity)
3. **Orbital Proximity Graph** (highest analytical value, complex calculations)
4. **Temporal Launch Sequence** (moderate complexity, good storytelling)

### Phase 3: Advanced Analytics (Medium Priority)
5. **Country Relations Graph** (requires aggregation, geopolitical interest)
6. **Function Similarity Network** (requires NLP/classification)

---

## Data Model Changes

### New Collections to Create

#### Edge Collections (ArangoDB Graph)
```python
# In db.py - add new collections
EDGE_COLLECTIONS = {
    "constellation_membership": {
        "from": "satellites",
        "to": "satellites"  # or constellation_hubs
    },
    "orbital_proximity": {
        "from": "satellites",
        "to": "satellites"
    },
    "launch_sequence": {
        "from": "satellites",
        "to": "satellites"
    },
    "registration_links": {
        "from": "satellites",
        "to": "registration_documents"
    },
    "function_similarity": {
        "from": "satellites",
        "to": "satellites"
    }
}
```

#### New Document Collection
```python
# registration_documents collection
{
  "_key": "stsgser_e1309",  # extracted from path
  "path": "/osoindex/data/documents/ru/st/stsgser.e1309.html",
  "url": "https://www.unoosa.org/...",
  "satellite_count": 6,
  "country": "Russian Federation",
  "submission_date": "2025-09-13",
  "satellites": ["2025-206A", "2025-206B", ...]
}
```

### Graph Definition
```python
# ArangoDB Named Graph
GRAPH_NAME = "satellite_relationships"
GRAPH_EDGE_DEFINITIONS = [
    {
        "edge_collection": "constellation_membership",
        "from_vertex_collections": ["satellites"],
        "to_vertex_collections": ["satellites"]
    },
    {
        "edge_collection": "orbital_proximity",
        "from_vertex_collections": ["satellites"],
        "to_vertex_collections": ["satellites"]
    },
    # ... other edge definitions
]
```

---

## API Endpoints to Create

### Graph Query Endpoints

```python
# In api.py

@app.get("/api/graphs/constellation/{constellation_name}")
def get_constellation_graph(constellation_name: str):
    """Return graph data for a specific constellation"""
    pass

@app.get("/api/graphs/orbital-proximity")
def get_orbital_proximity_graph(
    orbital_band: Optional[str] = None,
    congestion_risk: Optional[str] = None,
    limit: int = 100
):
    """Return satellites with orbital proximity relationships"""
    pass

@app.get("/api/graphs/country/{country_name}")
def get_country_satellites_graph(country_name: str):
    """Return all satellites for a country with relationships"""
    pass

@app.get("/api/graphs/launch-timeline")
def get_launch_timeline_graph(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    country: Optional[str] = None
):
    """Return temporal graph of satellite launches"""
    pass

@app.get("/api/graphs/registration-document/{doc_id}")
def get_registration_document_satellites(doc_id: str):
    """Return satellites linked to a registration document"""
    pass

@app.get("/api/graphs/function-similarity/{satellite_id}")
def get_function_similar_satellites(
    satellite_id: str,
    limit: int = 20
):
    """Find satellites with similar functions"""
    pass

@app.get("/api/graphs/stats")
def get_graph_statistics():
    """Return overall graph statistics (node counts, edge counts, etc.)"""
    pass
```

### Graph Data Format (Standard Response)

```json
{
  "nodes": [
    {
      "id": "2025-206B",
      "label": "(GLONASS)",
      "type": "satellite",
      "properties": {
        "country": "Russian Federation",
        "orbital_band": "MEO",
        "congestion_risk": "MEDIUM",
        "status": "in orbit"
      }
    }
  ],
  "edges": [
    {
      "id": "edge_123",
      "source": "2025-206B",
      "target": "2025-206A",
      "type": "constellation_membership",
      "properties": {
        "constellation": "Glonass",
        "weight": 1.0
      }
    }
  ],
  "metadata": {
    "node_count": 150,
    "edge_count": 423,
    "graph_type": "constellation"
  }
}
```

---

## Frontend Visualization

### Recommended Libraries

#### Option 1: D3.js (Most Flexible)
- **Pros**: Maximum customization, force-directed layouts, excellent for complex graphs
- **Cons**: Steeper learning curve, more code to write
- **Use Case**: Custom, branded visualizations with unique interactions

#### Option 2: Cytoscape.js (Recommended)
- **Pros**: Purpose-built for graphs, excellent performance, many layout algorithms
- **Cons**: Requires separate library, learning curve
- **Use Case**: Network analysis, biological networks, relationship maps
- **NPM**: `cytoscape`

#### Option 3: Vis.js Network (Easiest)
- **Pros**: Simple API, good defaults, interactive out-of-the-box
- **Cons**: Less customization than D3, may have performance issues with large graphs
- **Use Case**: Quick prototypes, simpler relationship visualizations
- **NPM**: `vis-network`

#### Option 4: React Flow (React-Native)
- **Pros**: React-first design, node-based workflows, modern API
- **Cons**: More suited for flow diagrams than network graphs
- **Use Case**: Process flows, decision trees
- **NPM**: `reactflow`

**Recommendation**: **Cytoscape.js** for production-quality graph visualization with good performance

### New React Components

```
react-app/src/components/
├── graphs/
│   ├── GraphViewer.jsx           # Main graph visualization component
│   ├── ConstellationGraph.jsx    # Constellation-specific view
│   ├── OrbitalProximityGraph.jsx # Proximity visualization
│   ├── LaunchTimeline.jsx        # Temporal graph
│   ├── CountryRelationsGraph.jsx # Country network
│   ├── GraphControls.jsx         # Layout, filter controls
│   ├── GraphLegend.jsx           # Visual legend for node/edge types
│   └── GraphStats.jsx            # Statistics panel
```

### UI Integration

**New Route/Tab**: Add "Graphs" tab to main navigation

**Graph Selection UI**:
- Dropdown to select graph type
- Filters for orbital band, country, date range, congestion risk
- Layout algorithm selector (force-directed, hierarchical, circular)
- Export options (PNG, SVG, JSON)

---

## Database Migration & Setup

### Migration Script

Create `migrate_graph_structure.py`:

```python
#!/usr/bin/env python3
"""
Create graph collections and build initial edge relationships
"""

def create_graph_collections():
    """Create edge collections and named graph"""
    # Create edge collections
    # Create registration_documents collection
    # Define named graph
    pass

def build_constellation_edges():
    """Build constellation membership edges"""
    pass

def build_registration_edges():
    """Build registration document edges"""
    pass

def build_temporal_edges():
    """Build launch sequence edges"""
    pass

def build_orbital_proximity_edges():
    """Calculate and build orbital proximity edges (intensive)"""
    pass
```

### Performance Considerations

**Edge Creation Strategy**:
- Build edges in batches (500-1000 at a time)
- Use AQL queries to create edges from existing document properties
- Cache expensive calculations (orbital proximity scores)

**Query Optimization**:
- Add indexes on edge collections: `_from`, `_to`, edge type fields
- Use `LIMIT` in graph traversals for large graphs
- Consider materialized graph views for frequent queries

**Estimated Edge Counts**:
- Constellation membership: ~19,000 edges (one per satellite)
- Registration links: ~19,000 edges
- Launch sequence: ~19,000 edges (chain structure)
- Orbital proximity: 10,000-100,000+ edges (most expensive, needs filtering)
- Function similarity: Variable (depends on classification)

---

## Verification & Testing Approach

### Unit Tests (Python)
- Test edge creation logic
- Test proximity calculation algorithms
- Test graph query functions
- Mock ArangoDB for isolated tests

### Integration Tests
- Test graph API endpoints
- Verify graph traversal queries return expected results
- Test pagination and limits on large graphs
- Performance benchmarks for graph queries

### Frontend Tests
- Component rendering tests (React Testing Library)
- Mock API responses for graph data
- Interaction tests (clicking nodes, filtering)

### Manual Testing
- Visual inspection of graph layouts
- Verify edge relationships make semantic sense
- Test with various filters and parameters
- Performance testing with large subgraphs

### Test Commands
```bash
# Backend tests
pytest test_graph_api.py
pytest test_graph_db.py

# Frontend tests
cd react-app
npm run test

# Integration tests
pytest test_graph_integration.py
```

---

## Risks & Challenges

### Technical Risks
1. **Performance**: Orbital proximity calculation may be O(n²) - mitigate with spatial indexing or sampling
2. **Graph Size**: Full graphs may be too large to visualize - implement smart filtering and sampling
3. **Data Quality**: Inconsistent or missing orbital parameters - handle gracefully with null checks
4. **Frontend Performance**: Rendering thousands of nodes may be slow - implement virtualization or LOD

### Data Risks
1. **Constellation Data**: Only 3 constellations identified - may need manual curation or classification
2. **Launch Vehicle Data**: Currently 0 entries - feature may be limited until data is enriched
3. **Incomplete Orbital Data**: Some satellites lack apogee/perigee - proximity graph will be partial

### Mitigation Strategies
- Start with simpler graphs (registration, constellation) to prove concept
- Implement progressive loading and lazy edge creation
- Add data quality checks and warnings in UI
- Use sampling for very large graphs (show top N by relevance)

---

## Success Metrics

### Technical Metrics
- Graph queries complete in <2 seconds for subgraphs of <1000 nodes
- Frontend renders graphs smoothly (60fps) for <500 nodes
- Edge creation completes in <5 minutes for all graph types

### User Value Metrics
- Constellation graphs clearly show mega-constellation structure
- Orbital proximity reveals congestion hotspots
- Country graphs show geopolitical patterns
- Launch timeline shows deployment trends

### Adoption Metrics
- Graph features used in >20% of user sessions
- Users explore multiple graph types
- Export functionality used regularly

---

## Dependencies to Add

### Python Backend
```bash
pip install python-arango  # Already installed
# No new Python dependencies needed
```

### React Frontend
```bash
cd react-app
npm install cytoscape
npm install cytoscape-dom-node  # For custom node rendering
npm install cytoscape-cola      # For layout algorithms
```

Alternative (if using vis.js):
```bash
npm install vis-network
```

---

## Timeline Estimate

**Phase 1 (Foundation)**: 2-3 days
- Create edge collections and graph structure
- Build registration document network
- Build constellation membership graph
- Basic API endpoints
- Simple frontend graph viewer

**Phase 2 (Core Analytics)**: 3-4 days
- Orbital proximity calculation and edges
- Launch sequence graph
- Enhanced API endpoints
- Improved frontend with filters and controls
- Graph statistics

**Phase 3 (Advanced Features)**: 2-3 days
- Country relations aggregation
- Function similarity (with basic NLP)
- Advanced layouts and visualizations
- Export capabilities
- Performance optimization

**Total**: 7-10 days for full implementation

---

## Conclusion

The satellite database contains rich relational data that is currently underutilized. By implementing ArangoDB's native graph capabilities, we can unlock powerful visualization and analysis features:

**Highest Value Graphs**:
1. **Orbital Proximity** - collision risk and congestion analysis
2. **Constellation Networks** - mega-constellation tracking
3. **Launch Timeline** - deployment trend analysis

**Recommended Approach**:
- Start with simple graphs (registration, constellation) to establish infrastructure
- Progress to more complex analytics (orbital proximity, country relations)
- Use Cytoscape.js for professional graph visualizations
- Implement smart filtering and sampling for performance

This will transform Kessler from a satellite registry viewer into a comprehensive space situational awareness platform with network analysis capabilities.

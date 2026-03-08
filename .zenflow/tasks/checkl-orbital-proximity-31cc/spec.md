# Technical Specification: Orbital Proximity Score of 0,00 for Satellites 66315 and 39634

## Difficulty Assessment
**Easy** — Investigation of an existing data display issue. The underlying calculation is correct; the problem is insufficient display precision.

---

## Technical Context

- **Language**: Python (backend / data population), JavaScript/React (frontend display)
- **Score computation**: [`scripts/population/populate_orbital_proximity.py`](../../../scripts/population/populate_orbital_proximity.py) — `calculate_proximity_score()`
- **Score display**: [`react-app/src/components/GraphViewer.jsx`](../../../react-app/src/components/GraphViewer.jsx) lines 1186 and 1575; [`react-app/src/components/SatelliteNeighborhood.jsx`](../../../react-app/src/components/SatelliteNeighborhood.jsx) line 355
- **Database**: ArangoDB — edge collection `orbital_proximity`

---

## Root Cause Analysis

### Satellites involved
| Identifier    | Name         | Apogee (km) | Perigee (km) | Inclination (°) | Band      |
|---------------|--------------|-------------|--------------|-----------------|-----------|
| NORAD-39634   | Sentinel-1A  | 696.64      | 694.87       | 98.18           | LEO-Polar |
| NORAD-66315   | Sentinel-1D  | 696.38      | 694.50       | 98.18           | LEO-Polar |

Both are members of the ESA Copernicus Sentinel-1 constellation and share an almost identical Sun-synchronous polar orbit by design.

### Score formula (populate_orbital_proximity.py)
```python
APOGEE_THRESHOLD_KM    = 50
PERIGEE_THRESHOLD_KM   = 50
INCLINATION_THRESHOLD_DEG = 5

score = (apogee_diff / 50)**2 + (perigee_diff / 50)**2 + (inclination_diff / 5)**2
```

### Computation for this pair
```
apogee_diff      = |696.64 - 696.38| = 0.26 km
perigee_diff     = |694.87 - 694.50| = 0.37 km
inclination_diff = |98.18  - 98.18 | = 0.00 °

score = (0.26/50)² + (0.37/50)² + (0.00/5)²
      = 0.00002704 + 0.00005476 + 0
      = 0.0000818  →  round(score, 4)  =  0.0001
```

The stored value in the database edge `orbital_proximity/31921` is **0.0001**, which is confirmed by:
```json
{"_key": "31921", "_from": "satellites/NORAD-39634", "_to": "satellites/NORAD-66315",
 "proximity_score": 0.0001, "apogee_diff_km": 0.26, "perigee_diff_km": 0.37, "inclination_diff_degrees": 0}
```

### Display issue
Both components render the score with `.toFixed(2)`:

```jsx
// GraphViewer.jsx:1186
` (score: ${parseFloat(edge.proximity_score).toFixed(2)})`

// GraphViewer.jsx:1575
`${edge.proximity_score.toFixed(2)}`

// SatelliteNeighborhood.jsx:355
{dataRanges.proximityScore.min.toFixed(2)}
```

`(0.0001).toFixed(2)` → `"0.00"` — the value is correct but the display precision truncates the significant digits.

### Conclusion
The "0,00" score is **not a bug in the calculation** — it accurately reflects that Sentinel-1A and Sentinel-1D orbit at essentially the same altitude, inclination, and band (by design). The score of 0.0001 is the closest possible pair in the dataset. The problem is purely cosmetic: `.toFixed(2)` is not enough precision for scores this small.

---

## Implementation Approach

Change the proximity score display from `.toFixed(2)` to `.toFixed(4)` in both components:

1. **[`GraphViewer.jsx`](../../../react-app/src/components/GraphViewer.jsx)** — 2 occurrences (lines 1186 and 1575)
2. **[`SatelliteNeighborhood.jsx`](../../../react-app/src/components/SatelliteNeighborhood.jsx)** — 1 occurrence (line 355, the range display `min.toFixed(2)` / `max.toFixed(2)`)

This will display "0.0001" instead of "0.00", making the score meaningful while still being compact.

---

## Source Code Changes

| File | Change |
|------|--------|
| `react-app/src/components/GraphViewer.jsx` | Replace `.toFixed(2)` with `.toFixed(4)` for `proximity_score` display (2 locations) |
| `react-app/src/components/SatelliteNeighborhood.jsx` | Replace `.toFixed(2)` with `.toFixed(4)` for `proximityScore` range display |

No backend, API, data model, or schema changes are needed.

---

## Verification Approach

1. Start the app with `./start.sh`
2. Open the Graph Viewer and navigate to the orbital proximity edge between NORAD-39634 (Sentinel-1A) and NORAD-66315 (Sentinel-1D)
3. Confirm the edge label/tooltip shows "0.0001" instead of "0.00"
4. Open the Satellite Neighborhood view for either satellite and confirm the proximity score range shows 4 decimal places
5. Run linter: `cd react-app && npm run lint` (if configured)

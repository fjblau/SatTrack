import { useState, useEffect } from 'react'
import './SatelliteNeighborhood.css'

function SatelliteNeighborhood({ onNeighborhoodLoad }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [selectedSatellite, setSelectedSatellite] = useState(null)
  const [loading, setLoading] = useState(false)
  const [neighborhoodData, setNeighborhoodData] = useState(null)
  const [rawNeighborhoodData, setRawNeighborhoodData] = useState(null)
  const [error, setError] = useState(null)
  const [edgeTypes, setEdgeTypes] = useState(['orbital_proximity'])
  const [proximityFilters, setProximityFilters] = useState({
    maxProximityScore: 2.0,
    maxDistance: 50,
    maxInclinationDiff: 5
  })
  const [dataRanges, setDataRanges] = useState({
    proximityScore: { min: 0.01, max: 5.0 },
    distance: { min: 5, max: 100 },
    inclinationDiff: { min: 0.5, max: 10 }
  })

  // Re-apply filters when proximity filters change
  useEffect(() => {
    if (rawNeighborhoodData) {
      applyFilters(rawNeighborhoodData)
    }
  }, [proximityFilters])

  const calculateDataRanges = (data) => {
    if (!data.edges || data.edges.length === 0) {
      return {
        proximityScore: { min: 0.01, max: 5.0 },
        distance: { min: 5, max: 100 },
        inclinationDiff: { min: 0.5, max: 10 }
      }
    }

    const proximityEdges = data.edges.filter(e => e.type === 'orbital_proximity')
    
    if (proximityEdges.length === 0) {
      return {
        proximityScore: { min: 0.01, max: 5.0 },
        distance: { min: 5, max: 100 },
        inclinationDiff: { min: 0.5, max: 10 }
      }
    }

    const proximityScores = proximityEdges.map(e => e.proximity_score).filter(v => v != null)
    const apogees = proximityEdges.map(e => e.apogee_diff_km).filter(v => v != null)
    const perigees = proximityEdges.map(e => e.perigee_diff_km).filter(v => v != null)
    const distances = [...apogees, ...perigees]
    const inclinations = proximityEdges.map(e => e.inclination_diff_degrees).filter(v => v != null)

    return {
      proximityScore: {
        min: proximityScores.length > 0 ? Math.min(...proximityScores) : 0.01,
        max: proximityScores.length > 0 ? Math.max(...proximityScores) : 5.0
      },
      distance: {
        min: distances.length > 0 ? Math.min(...distances) : 5,
        max: distances.length > 0 ? Math.max(...distances) : 100
      },
      inclinationDiff: {
        min: inclinations.length > 0 ? Math.min(...inclinations) : 0.5,
        max: inclinations.length > 0 ? Math.max(...inclinations) : 10
      }
    }
  }

  const applyFilters = (data, filters = null) => {
    // Use provided filters or current state
    const activeFilters = filters || proximityFilters
    
    // Pass 1: Identify valid nodes based on orbital proximity edges
    const validNodeIds = new Set()
    const sourceNode = data.nodes.find(n => n.is_source)
    if (sourceNode) {
      validNodeIds.add(sourceNode.id || sourceNode._id)
    }
    
    // Add nodes connected by valid orbital_proximity edges
    if (edgeTypes.includes('orbital_proximity') && data.edges) {
      data.edges.forEach(edge => {
        if (edge.type === 'orbital_proximity') {
          // Check if edge meets proximity filters
          let meetsFilters = true
          
          if (edge.proximity_score != null && edge.proximity_score > activeFilters.maxProximityScore) {
            meetsFilters = false
          }
          if (edge.apogee_diff_km != null && edge.apogee_diff_km > activeFilters.maxDistance) {
            meetsFilters = false
          }
          if (edge.perigee_diff_km != null && edge.perigee_diff_km > activeFilters.maxDistance) {
            meetsFilters = false
          }
          if (edge.inclination_diff_degrees != null && edge.inclination_diff_degrees > activeFilters.maxInclinationDiff) {
            meetsFilters = false
          }
          
          if (meetsFilters) {
            validNodeIds.add(edge.source || edge._from)
            validNodeIds.add(edge.target || edge._to)
          }
        }
      })
    }
    
    // Pass 2: Filter edges - keep only if both endpoints are valid nodes
    const filteredEdges = data.edges ? data.edges.filter(edge => {
      const source = edge.source || edge._from
      const target = edge.target || edge._to
      
      // Both endpoints must be valid nodes
      if (!validNodeIds.has(source) || !validNodeIds.has(target)) {
        return false
      }
      
      // For orbital_proximity edges, also check filter criteria
      if (edge.type === 'orbital_proximity') {
        if (edge.proximity_score != null && edge.proximity_score > activeFilters.maxProximityScore) {
          return false
        }
        if (edge.apogee_diff_km != null && edge.apogee_diff_km > activeFilters.maxDistance) {
          return false
        }
        if (edge.perigee_diff_km != null && edge.perigee_diff_km > activeFilters.maxDistance) {
          return false
        }
        if (edge.inclination_diff_degrees != null && edge.inclination_diff_degrees > activeFilters.maxInclinationDiff) {
          return false
        }
      }
      
      return true
    }) : []
    
    // Filter nodes to only valid ones
    const filteredNodes = data.nodes.filter(node => 
      validNodeIds.has(node.id || node._id)
    )
    
    const filteredData = {
      ...data,
      nodes: filteredNodes,
      edges: filteredEdges
    }
    
    setNeighborhoodData(filteredData)
    if (onNeighborhoodLoad) {
      onNeighborhoodLoad(filteredData, selectedSatellite)
    }
  }

  const searchSatellites = async (query) => {
    if (query.length < 2) {
      setSearchResults([])
      return
    }

    setSearching(true)
    try {
      const response = await fetch(`/v2/search?q=${encodeURIComponent(query)}&limit=10`)
      const result = await response.json()
      
      if (result.data && Array.isArray(result.data)) {
        setSearchResults(result.data.map(sat => ({
          id: sat.identifier,
          name: sat.canonical?.name || sat.identifier || 'Unknown',
          identifier: sat.identifier,
          country: sat.canonical?.country,
          constellation: sat.canonical?.constellation
        })))
      }
    } catch (err) {
      console.error('Search error:', err)
    } finally {
      setSearching(false)
    }
  }

  const loadNeighborhood = async (satelliteId) => {
    setLoading(true)
    setError(null)
    
    try {
      const params = new URLSearchParams({
        depth: '2',
        limit: '100'
      })
      
      edgeTypes.forEach(type => params.append('edge_types', type))
      
      const response = await fetch(`/v2/graphs/satellite/${encodeURIComponent(satelliteId)}/neighborhood?${params}`)
      
      if (!response.ok) {
        throw new Error(`Failed to load neighborhood: ${response.statusText}`)
      }
      
      const result = await response.json()
      
      if (result.data) {
        // Calculate ranges from actual data
        const ranges = calculateDataRanges(result.data)
        setDataRanges(ranges)
        
        // Initialize filters to show all data (use max values)
        const initialFilters = {
          maxProximityScore: ranges.proximityScore.max,
          maxDistance: ranges.distance.max,
          maxInclinationDiff: ranges.inclinationDiff.max
        }
        setProximityFilters(initialFilters)
        
        // Store raw data and apply filters with initial values
        setRawNeighborhoodData(result.data)
        applyFilters(result.data, initialFilters)
      } else {
        throw new Error('Invalid response format')
      }
    } catch (err) {
      console.error('Error loading neighborhood:', err)
      setError(err.message)
      setNeighborhoodData(null)
    } finally {
      setLoading(false)
    }
  }

  const handleSatelliteSelect = (satellite) => {
    setSelectedSatellite(satellite)
    setSearchQuery(satellite.name)
    setSearchResults([])
    loadNeighborhood(satellite.id)
  }

  const handleEdgeTypeToggle = (type) => {
    setEdgeTypes(prev => {
      const newTypes = prev.includes(type) 
        ? prev.filter(t => t !== type)
        : [...prev, type]
      return newTypes.length > 0 ? newTypes : prev
    })
  }

  return (
    <div className="satellite-neighborhood">
      <div className="neighborhood-header">
        <h3>Satellite Neighborhood Explorer</h3>
        <p className="section-description">
          Search for a satellite and explore its local network connections
        </p>
      </div>

      <div className="search-section">
        <div className="search-container">
          <input
            type="text"
            placeholder="Search satellites by name or identifier..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              searchSatellites(e.target.value)
            }}
            className="satellite-search-input"
          />
          {searching && <span className="search-indicator">Searching...</span>}
        </div>

        {searchResults.length > 0 && (
          <div className="search-results">
            {searchResults.map((satellite) => (
              <div
                key={satellite.id}
                className="search-result-item"
                onClick={() => handleSatelliteSelect(satellite)}
              >
                <div className="result-name">{satellite.name}</div>
                <div className="result-details">
                  {satellite.constellation && <span className="detail-badge">{satellite.constellation}</span>}
                  {satellite.country && <span className="detail-badge">{satellite.country}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedSatellite && (
        <div className="selected-satellite">
          <div className="satellite-info">
            <strong>{selectedSatellite.name}</strong>
            {selectedSatellite.constellation && <span className="info-badge">{selectedSatellite.constellation}</span>}
          </div>
          <button 
            className="clear-button"
            onClick={() => {
              setSelectedSatellite(null)
              setSearchQuery('')
              setNeighborhoodData(null)
            }}
          >
            Clear
          </button>
        </div>
      )}

      <div className="edge-type-filters">
        <label className="filter-label">Connection Types:</label>
        <div className="filter-buttons">
          <button
            className={`filter-button ${edgeTypes.includes('orbital_proximity') ? 'active' : ''}`}
            onClick={() => handleEdgeTypeToggle('orbital_proximity')}
          >
            Orbital Proximity
          </button>
          <button
            className={`filter-button ${edgeTypes.includes('constellation_membership') ? 'active' : ''}`}
            onClick={() => handleEdgeTypeToggle('constellation_membership')}
          >
            Constellation
          </button>
          <button
            className={`filter-button ${edgeTypes.includes('registration_links') ? 'active' : ''}`}
            onClick={() => handleEdgeTypeToggle('registration_links')}
          >
            Registration
          </button>
        </div>

        {edgeTypes.includes('orbital_proximity') && (
          <div className="proximity-filters">
            <label className="filter-label">Orbital Proximity Filters:</label>
            <div className="filter-sliders">
              <div className="filter-slider">
                <label>
                  Max Proximity Score: <strong>{proximityFilters.maxProximityScore.toFixed(2)}</strong>
                  <span className="filter-help">
                    (range: {dataRanges.proximityScore.min.toFixed(2)} - {dataRanges.proximityScore.max.toFixed(2)})
                  </span>
                </label>
                <input
                  type="range"
                  min={dataRanges.proximityScore.min}
                  max={dataRanges.proximityScore.max}
                  step={(dataRanges.proximityScore.max - dataRanges.proximityScore.min) / 100}
                  value={proximityFilters.maxProximityScore}
                  onChange={(e) => setProximityFilters({...proximityFilters, maxProximityScore: parseFloat(e.target.value)})}
                />
              </div>
              <div className="filter-slider">
                <label>
                  Max Orbital Distance: <strong>{proximityFilters.maxDistance.toFixed(1)} km</strong>
                  <span className="filter-help">
                    (range: {dataRanges.distance.min.toFixed(1)} - {dataRanges.distance.max.toFixed(1)} km)
                  </span>
                </label>
                <input
                  type="range"
                  min={dataRanges.distance.min}
                  max={dataRanges.distance.max}
                  step={(dataRanges.distance.max - dataRanges.distance.min) / 100}
                  value={proximityFilters.maxDistance}
                  onChange={(e) => setProximityFilters({...proximityFilters, maxDistance: parseFloat(e.target.value)})}
                />
              </div>
              <div className="filter-slider">
                <label>
                  Max Inclination Diff: <strong>{proximityFilters.maxInclinationDiff.toFixed(2)}°</strong>
                  <span className="filter-help">
                    (range: {dataRanges.inclinationDiff.min.toFixed(2)} - {dataRanges.inclinationDiff.max.toFixed(2)}°)
                  </span>
                </label>
                <input
                  type="range"
                  min={dataRanges.inclinationDiff.min}
                  max={dataRanges.inclinationDiff.max}
                  step={(dataRanges.inclinationDiff.max - dataRanges.inclinationDiff.min) / 100}
                  value={proximityFilters.maxInclinationDiff}
                  onChange={(e) => setProximityFilters({...proximityFilters, maxInclinationDiff: parseFloat(e.target.value)})}
                />
              </div>
            </div>
          </div>
        )}

        {selectedSatellite && (
          <button 
            className="reload-button"
            onClick={() => loadNeighborhood(selectedSatellite.id)}
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Reload Neighborhood'}
          </button>
        )}
      </div>

      {error && (
        <div className="error-message">
          ⚠️ {error}
        </div>
      )}

      {neighborhoodData && !loading && (
        <div className="neighborhood-stats">
          <h4>Network Statistics</h4>
          <div className="stats-grid">
            <div className="stat-item">
              <span className="stat-label">Neighbors:</span>
              <span className="stat-value">{neighborhoodData.nodes?.length || 0}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Connections:</span>
              <span className="stat-value">{neighborhoodData.edges?.length || 0}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Max Depth:</span>
              <span className="stat-value">2 hops</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SatelliteNeighborhood

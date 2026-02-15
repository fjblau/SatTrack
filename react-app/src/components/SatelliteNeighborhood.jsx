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

  // Re-apply filters when proximity filters change
  useEffect(() => {
    if (rawNeighborhoodData) {
      applyFilters(rawNeighborhoodData)
    }
  }, [proximityFilters])

  const applyFilters = (data) => {
    // Apply proximity filters if orbital_proximity edges are included
    const filteredData = {...data}
    if (edgeTypes.includes('orbital_proximity') && data.edges) {
      filteredData.edges = data.edges.filter(edge => {
        // If not an orbital proximity edge, keep it
        if (edge.type !== 'orbital_proximity') return true
        
        // Apply proximity filters
        if (edge.proximity_score != null && edge.proximity_score > proximityFilters.maxProximityScore) {
          return false
        }
        
        // Apply distance filter (check apogee and perigee differences)
        if (edge.apogee_diff_km != null && edge.apogee_diff_km > proximityFilters.maxDistance) {
          return false
        }
        if (edge.perigee_diff_km != null && edge.perigee_diff_km > proximityFilters.maxDistance) {
          return false
        }
        
        // Apply inclination filter
        if (edge.inclination_diff_degrees != null && edge.inclination_diff_degrees > proximityFilters.maxInclinationDiff) {
          return false
        }
        
        return true
      })
      
      // Also filter out nodes that have no edges anymore
      const connectedNodeIds = new Set()
      filteredData.edges.forEach(edge => {
        connectedNodeIds.add(edge.source || edge._from)
        connectedNodeIds.add(edge.target || edge._to)
      })
      
      filteredData.nodes = data.nodes.filter(node => {
        return node.is_source || connectedNodeIds.has(node.id || node._id)
      })
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
        // Store raw data and apply filters
        setRawNeighborhoodData(result.data)
        applyFilters(result.data)
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
                  <span className="filter-help">(lower = closer)</span>
                </label>
                <input
                  type="range"
                  min="0.01"
                  max="5.0"
                  step="0.05"
                  value={proximityFilters.maxProximityScore}
                  onChange={(e) => setProximityFilters({...proximityFilters, maxProximityScore: parseFloat(e.target.value)})}
                />
              </div>
              <div className="filter-slider">
                <label>
                  Max Orbital Distance: <strong>{proximityFilters.maxDistance} km</strong>
                  <span className="filter-help">(apogee/perigee diff)</span>
                </label>
                <input
                  type="range"
                  min="5"
                  max="100"
                  step="5"
                  value={proximityFilters.maxDistance}
                  onChange={(e) => setProximityFilters({...proximityFilters, maxDistance: parseInt(e.target.value)})}
                />
              </div>
              <div className="filter-slider">
                <label>
                  Max Inclination Diff: <strong>{proximityFilters.maxInclinationDiff}°</strong>
                </label>
                <input
                  type="range"
                  min="0.5"
                  max="10"
                  step="0.5"
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

import { useState } from 'react'
import './SatelliteNeighborhood.css'

function SatelliteNeighborhood({ onNeighborhoodLoad }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [selectedSatellite, setSelectedSatellite] = useState(null)
  const [loading, setLoading] = useState(false)
  const [neighborhoodData, setNeighborhoodData] = useState(null)
  const [error, setError] = useState(null)
  const [edgeTypes, setEdgeTypes] = useState(['orbital_proximity'])

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
        setNeighborhoodData(result.data)
        if (onNeighborhoodLoad) {
          onNeighborhoodLoad(result.data, selectedSatellite)
        }
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

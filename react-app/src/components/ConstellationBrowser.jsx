import { useState, useEffect } from 'react'
import './ConstellationBrowser.css'

function ConstellationBrowser({ constellations, onConstellationSelect }) {
  const [selectedConstellation, setSelectedConstellation] = useState(null)
  const [loading, setLoading] = useState(false)
  const [networkData, setNetworkData] = useState(null)
  const [error, setError] = useState(null)

  const loadConstellationNetwork = async (constellationName) => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`/v2/graphs/constellation/${encodeURIComponent(constellationName)}?limit=100`)
      
      if (!response.ok) {
        throw new Error(`Failed to load constellation: ${response.statusText}`)
      }
      
      const result = await response.json()
      
      if (result.data && result.data.nodes) {
        setNetworkData(result.data)
        if (onConstellationSelect) {
          onConstellationSelect(result.data, constellationName)
        }
      } else {
        throw new Error('Invalid response format')
      }
    } catch (err) {
      console.error('Error loading constellation:', err)
      setError(err.message)
      setNetworkData(null)
    } finally {
      setLoading(false)
    }
  }

  const handleConstellationClick = (constellation) => {
    setSelectedConstellation(constellation)
    loadConstellationNetwork(constellation.name)
  }

  return (
    <div className="constellation-browser">
      <div className="constellation-header">
        <h3>Constellation Networks</h3>
        <p className="section-description">
          Explore satellite constellations and their network topology
        </p>
      </div>

      <div className="constellation-grid">
        {constellations && constellations.length > 0 ? (
          constellations.map((constellation) => (
            <div
              key={constellation.name}
              className={`constellation-card ${selectedConstellation?.name === constellation.name ? 'selected' : ''}`}
              onClick={() => handleConstellationClick(constellation)}
            >
              <div className="constellation-name">{constellation.name}</div>
              <div className="constellation-count">
                {constellation.member_count.toLocaleString()} satellites
              </div>
              {selectedConstellation?.name === constellation.name && loading && (
                <div className="loading-indicator">Loading...</div>
              )}
            </div>
          ))
        ) : (
          <div className="no-data">No constellations available</div>
        )}
      </div>

      {error && (
        <div className="error-message">
          ⚠️ {error}
        </div>
      )}

      {networkData && !loading && (
        <div className="network-stats">
          <h4>Network Statistics</h4>
          <div className="stats-grid">
            <div className="stat-item">
              <span className="stat-label">Nodes:</span>
              <span className="stat-value">{networkData.nodes.length}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Edges:</span>
              <span className="stat-value">{networkData.edges.length}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Constellation:</span>
              <span className="stat-value">{selectedConstellation?.name}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ConstellationBrowser

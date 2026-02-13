import { useState, useEffect } from 'react'
import './CollisionRiskView.css'

function CollisionRiskView({ onCollisionRiskSelect }) {
  const [viewType, setViewType] = useState('network')
  const [riskThreshold, setRiskThreshold] = useState(0.5)
  const [orbitalBands, setOrbitalBands] = useState([])
  const [selectedOrbitalBand, setSelectedOrbitalBand] = useState('')
  const [minClusterSize, setMinClusterSize] = useState(3)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadOrbitalBands()
  }, [])

  const loadOrbitalBands = async () => {
    try {
      const response = await fetch('/v2/graphs/stats')
      const data = await response.json()
      if (data.data?.proximity_by_orbital_band) {
        setOrbitalBands(data.data.proximity_by_orbital_band)
        if (data.data.proximity_by_orbital_band.length > 0) {
          setSelectedOrbitalBand(data.data.proximity_by_orbital_band[0].orbital_band)
        }
      }
    } catch (err) {
      console.error('Error loading orbital bands:', err)
    }
  }

  const handleLoadCollisionRisks = async () => {
    setLoading(true)
    setError(null)

    try {
      let endpoint
      let params = new URLSearchParams()

      if (viewType === 'network') {
        endpoint = '/v2/graphs/collision-risks/network/graph'
        params.append('risk_threshold', riskThreshold)
        if (selectedOrbitalBand) {
          params.append('orbital_band', selectedOrbitalBand)
        }
      } else if (viewType === 'clusters') {
        endpoint = '/v2/graphs/collision-risks/clusters'
        params.append('min_cluster_size', minClusterSize)
        if (selectedOrbitalBand) {
          params.append('orbital_band', selectedOrbitalBand)
        }
      }

      const response = await fetch(`${endpoint}?${params}`)
      const data = await response.json()

      if (response.ok && data.data) {
        onCollisionRiskSelect(data.data, viewType)
      } else {
        setError(data.message || 'Failed to load collision risks')
      }
    } catch (err) {
      setError('Error loading collision risks: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="collision-risk-view">
      <h3>Collision Risk Analysis</h3>
      <p className="panel-description">Analyze potential collision risks between satellites</p>
      
      <div className="collision-form">
        <div className="form-group">
          <label>View Type:</label>
          <select value={viewType} onChange={(e) => setViewType(e.target.value)}>
            <option value="network">Risk Network</option>
            <option value="clusters">Risk Clusters</option>
          </select>
        </div>

        <div className="form-group">
          <label>Orbital Band:</label>
          <select 
            value={selectedOrbitalBand} 
            onChange={(e) => setSelectedOrbitalBand(e.target.value)}
          >
            <option value="">All Bands</option>
            {orbitalBands.map(band => (
              <option key={band.orbital_band} value={band.orbital_band}>
                {band.orbital_band} ({band.edge_count.toLocaleString()} edges)
              </option>
            ))}
          </select>
        </div>

        {viewType === 'network' && (
          <div className="form-group">
            <label>Risk Threshold:</label>
            <input
              type="range"
              value={riskThreshold}
              onChange={(e) => setRiskThreshold(parseFloat(e.target.value))}
              min="0"
              max="1"
              step="0.1"
            />
            <span className="range-value">{riskThreshold.toFixed(1)}</span>
            <div className="range-labels">
              <span>Low Risk</span>
              <span>High Risk</span>
            </div>
          </div>
        )}

        {viewType === 'clusters' && (
          <div className="form-group">
            <label>Minimum Cluster Size:</label>
            <input
              type="number"
              value={minClusterSize}
              onChange={(e) => setMinClusterSize(parseInt(e.target.value))}
              min="2"
              max="50"
            />
          </div>
        )}

        <button 
          onClick={handleLoadCollisionRisks} 
          disabled={loading}
          className="load-button"
        >
          {loading ? 'Loading...' : 'Load Collision Risks'}
        </button>

        {error && <div className="error-message">{error}</div>}
      </div>

      <div className="risk-info">
        <h4>Risk Levels:</h4>
        <div className="risk-legend">
          <div className="risk-item">
            <span className="risk-badge critical"></span>
            <span>Critical (&gt;0.8)</span>
          </div>
          <div className="risk-item">
            <span className="risk-badge high"></span>
            <span>High (0.6-0.8)</span>
          </div>
          <div className="risk-item">
            <span className="risk-badge medium"></span>
            <span>Medium (0.4-0.6)</span>
          </div>
          <div className="risk-item">
            <span className="risk-badge low"></span>
            <span>Low (&lt;0.4)</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default CollisionRiskView

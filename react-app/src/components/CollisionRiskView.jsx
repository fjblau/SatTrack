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
  const [noResults, setNoResults] = useState(false)

  useEffect(() => {
    loadOrbitalBands()
  }, [])

  const loadOrbitalBands = async () => {
    try {
      console.log('[CollisionRiskView] Loading orbital bands...')
      const response = await fetch('/v2/graphs/stats')
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('[CollisionRiskView] Orbital bands response:', data)
      
      if (data.data?.proximity_by_orbital_band) {
        setOrbitalBands(data.data.proximity_by_orbital_band)
        if (data.data.proximity_by_orbital_band.length > 0) {
          setSelectedOrbitalBand(data.data.proximity_by_orbital_band[0].orbital_band)
        }
        console.log(`[CollisionRiskView] Loaded ${data.data.proximity_by_orbital_band.length} orbital bands`)
      }
    } catch (err) {
      console.error('[CollisionRiskView] Error loading orbital bands:', err)
    }
  }

  const handleLoadCollisionRisks = async () => {
    if (viewType === 'clusters' && (minClusterSize < 2 || minClusterSize > 50)) {
      setError('⚠️ Minimum cluster size must be between 2 and 50')
      return
    }

    if (viewType === 'network' && (riskThreshold < 0 || riskThreshold > 1)) {
      setError('⚠️ Risk threshold must be between 0 and 1')
      return
    }

    setLoading(true)
    setError(null)
    setNoResults(false)

    try {
      let endpoint
      let params = new URLSearchParams()

      if (viewType === 'network') {
        endpoint = '/v2/graphs/collision-risks/network/graph'
        params.append('risk_threshold', riskThreshold)
        if (selectedOrbitalBand) {
          params.append('orbital_band', selectedOrbitalBand)
        }
        console.log(`[CollisionRiskView] Loading network: threshold=${riskThreshold}, band=${selectedOrbitalBand || 'all'}`)
      } else if (viewType === 'clusters') {
        endpoint = '/v2/graphs/collision-risks/clusters'
        params.append('min_cluster_size', minClusterSize)
        if (selectedOrbitalBand) {
          params.append('orbital_band', selectedOrbitalBand)
        }
        console.log(`[CollisionRiskView] Loading clusters: min_size=${minClusterSize}, band=${selectedOrbitalBand || 'all'}`)
      }

      const response = await fetch(`${endpoint}?${params}`)
      
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.message || `HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('[CollisionRiskView] Response:', data)

      if (data.data) {
        const nodeCount = data.data.nodes?.length || 0
        const edgeCount = data.data.edges?.length || 0
        
        if (nodeCount === 0 && edgeCount === 0) {
          setNoResults(true)
          console.log('[CollisionRiskView] No results found')
        } else {
          console.log(`[CollisionRiskView] Success: ${nodeCount} nodes, ${edgeCount} edges`)
          onCollisionRiskSelect(data.data, viewType)
        }
      } else {
        throw new Error('Invalid response: missing data field')
      }
    } catch (err) {
      console.error('[CollisionRiskView] Error:', err)
      setError(`❌ Error loading collision risks: ${err.message}`)
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
          {loading ? (
            <>
              <span className="spinner"></span>
              Loading...
            </>
          ) : 'Load Collision Risks'}
        </button>

        {error && <div className="error-message">{error}</div>}
        {noResults && (
          <div className="no-results-message">
            ℹ️ No collision risks found with the selected parameters. Try:
            <ul>
              {viewType === 'network' && (
                <>
                  <li>Lowering the risk threshold</li>
                  <li>Selecting a different orbital band</li>
                  <li>Selecting "All Bands"</li>
                </>
              )}
              {viewType === 'clusters' && (
                <>
                  <li>Reducing the minimum cluster size</li>
                  <li>Selecting a different orbital band</li>
                  <li>Selecting "All Bands"</li>
                </>
              )}
            </ul>
          </div>
        )}
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

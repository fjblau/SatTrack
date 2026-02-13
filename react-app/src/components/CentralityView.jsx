import { useState } from 'react'
import './CentralityView.css'

function CentralityView({ onCentralitySelect }) {
  const [metricType, setMetricType] = useState('degree')
  const [edgeTypes, setEdgeTypes] = useState(['constellation', 'proximity', 'registration'])
  const [topN, setTopN] = useState(20)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [noResults, setNoResults] = useState(false)

  const handleEdgeTypeToggle = (edgeType) => {
    setEdgeTypes(prev => {
      if (prev.includes(edgeType)) {
        return prev.filter(t => t !== edgeType)
      } else {
        return [...prev, edgeType]
      }
    })
  }

  const handleCalculateCentrality = async () => {
    if (edgeTypes.length === 0) {
      setError('⚠️ Please select at least one edge type to calculate centrality')
      return
    }

    if (topN < 5 || topN > 100) {
      setError('⚠️ Top N must be between 5 and 100')
      return
    }

    setLoading(true)
    setError(null)
    setNoResults(false)

    try {
      const params = new URLSearchParams({
        metric: metricType,
        limit: topN
      })
      
      edgeTypes.forEach(type => {
        params.append('edge_types', type)
      })

      console.log(`[CentralityView] Fetching centrality: metric=${metricType}, edge_types=[${edgeTypes.join(',')}], limit=${topN}`)
      
      const response = await fetch(`/v2/graphs/analytics/centrality?${params}`)
      
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.message || `HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('[CentralityView] Response:', data)

      if (data.data) {
        if (data.data.satellites && data.data.satellites.length === 0) {
          setNoResults(true)
          console.log('[CentralityView] No results found')
        } else {
          console.log(`[CentralityView] Success: ${data.data.satellites?.length || 0} satellites`)
          onCentralitySelect(data.data, metricType)
        }
      } else {
        throw new Error('Invalid response: missing data field')
      }
    } catch (err) {
      console.error('[CentralityView] Error:', err)
      setError(`❌ Error calculating centrality: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="centrality-view">
      <h3>Centrality Analysis</h3>
      <p className="panel-description">Identify hub satellites and network importance</p>
      
      <div className="centrality-form">
        <div className="form-group">
          <label>Centrality Metric:</label>
          <select value={metricType} onChange={(e) => setMetricType(e.target.value)}>
            <option value="degree">Degree Centrality</option>
            <option value="betweenness">Betweenness Centrality</option>
            <option value="closeness">Closeness Centrality</option>
          </select>
        </div>

        <div className="form-group">
          <label>Edge Types:</label>
          <div className="edge-type-checkboxes">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={edgeTypes.includes('constellation')}
                onChange={() => handleEdgeTypeToggle('constellation')}
              />
              Constellation
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={edgeTypes.includes('proximity')}
                onChange={() => handleEdgeTypeToggle('proximity')}
              />
              Proximity
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={edgeTypes.includes('registration')}
                onChange={() => handleEdgeTypeToggle('registration')}
              />
              Registration
            </label>
          </div>
        </div>

        <div className="form-group">
          <label>Top N Nodes:</label>
          <input
            type="number"
            value={topN}
            onChange={(e) => setTopN(parseInt(e.target.value))}
            min="5"
            max="100"
          />
        </div>

        <button 
          onClick={handleCalculateCentrality} 
          disabled={loading}
          className="calculate-button"
        >
          {loading ? (
            <>
              <span className="spinner"></span>
              Calculating...
            </>
          ) : 'Calculate Centrality'}
        </button>

        {error && <div className="error-message">{error}</div>}
        {noResults && (
          <div className="no-results-message">
            ℹ️ No results found with the selected parameters. Try:
            <ul>
              <li>Selecting more edge types</li>
              <li>Increasing the Top N value</li>
              <li>Using a different centrality metric</li>
            </ul>
          </div>
        )}
      </div>

      <div className="metric-info">
        <h4>Metric Description:</h4>
        {metricType === 'degree' && (
          <p>Measures the number of direct connections a satellite has. Higher values indicate more connected satellites.</p>
        )}
        {metricType === 'betweenness' && (
          <p>Measures how often a satellite appears on shortest paths between other satellites. Higher values indicate satellites that act as bridges.</p>
        )}
        {metricType === 'closeness' && (
          <p>Measures how close a satellite is to all other satellites in the network. Higher values indicate more centrally located satellites.</p>
        )}
      </div>
    </div>
  )
}

export default CentralityView

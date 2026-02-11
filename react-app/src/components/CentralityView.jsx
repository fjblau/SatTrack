import { useState } from 'react'
import './CentralityView.css'

function CentralityView({ onCentralitySelect }) {
  const [metricType, setMetricType] = useState('degree')
  const [edgeTypes, setEdgeTypes] = useState(['constellation', 'proximity', 'registration'])
  const [topN, setTopN] = useState(20)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

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
      setError('Please select at least one edge type')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({
        metric: metricType,
        top_n: topN
      })
      
      edgeTypes.forEach(type => {
        params.append('edge_types', type)
      })

      const response = await fetch(`/v2/graphs/analytics/centrality?${params}`)
      const data = await response.json()

      if (response.ok && data.data) {
        onCentralitySelect(data.data, metricType)
      } else {
        setError(data.message || 'Failed to calculate centrality')
      }
    } catch (err) {
      setError('Error calculating centrality: ' + err.message)
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
          {loading ? 'Calculating...' : 'Calculate Centrality'}
        </button>

        {error && <div className="error-message">{error}</div>}
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

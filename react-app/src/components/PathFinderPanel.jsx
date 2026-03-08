import { useState } from 'react'
import './PathFinderPanel.css'

function PathFinderPanel({ onPathSelect }) {
  const [fromSatellite, setFromSatellite] = useState('')
  const [toSatellite, setToSatellite] = useState('')
  const [maxDepth, setMaxDepth] = useState(3)
  const [algorithm, setAlgorithm] = useState('shortest')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleFindPath = async () => {
    if (!fromSatellite || !toSatellite) {
      setError('Please enter both satellite identifiers')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({
        max_depth: maxDepth,
        algorithm: algorithm
      })

      const response = await fetch(`/v2/graphs/paths/${encodeURIComponent(fromSatellite)}/${encodeURIComponent(toSatellite)}?${params}`)
      const data = await response.json()

      if (response.ok && data.data) {
        onPathSelect(data.data)
      } else {
        setError(data.message || 'Failed to find path')
      }
    } catch (err) {
      setError('Error finding path: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="path-finder-panel">
      <h3>Path Finder</h3>
      <p className="panel-description">Find relationships between satellites</p>
      
      <p className="panel-hint">Enter a bare NORAD number (e.g. <strong>39634</strong>), a prefixed ID (e.g. <strong>NORAD-39634</strong>), or an international designator.</p>
      <div className="path-form">
        <div className="form-group">
          <label>From Satellite:</label>
          <input
            type="text"
            value={fromSatellite}
            onChange={(e) => setFromSatellite(e.target.value)}
            placeholder="e.g. 39634 or NORAD-39634"
          />
        </div>

        <div className="form-group">
          <label>To Satellite:</label>
          <input
            type="text"
            value={toSatellite}
            onChange={(e) => setToSatellite(e.target.value)}
            placeholder="e.g. 42969 or NORAD-42969"
          />
        </div>

        <div className="form-group">
          <label>Max Depth:</label>
          <input
            type="number"
            value={maxDepth}
            onChange={(e) => setMaxDepth(parseInt(e.target.value))}
            min="1"
            max="10"
          />
        </div>

        <div className="form-group">
          <label>Algorithm:</label>
          <select value={algorithm} onChange={(e) => setAlgorithm(e.target.value)}>
            <option value="shortest">Shortest Path</option>
            <option value="all">All Paths</option>
          </select>
        </div>

        <button 
          onClick={handleFindPath} 
          disabled={loading}
          className="find-path-button"
        >
          {loading ? 'Finding...' : 'Find Path'}
        </button>

        {error && <div className="error-message">{error}</div>}
      </div>
    </div>
  )
}

export default PathFinderPanel

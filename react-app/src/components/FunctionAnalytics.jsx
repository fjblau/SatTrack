import { useState, useEffect } from 'react'
import './FunctionAnalytics.css'
import { API_ENDPOINTS } from '../config/constants'

function FunctionAnalytics() {
  const [viewMode, setViewMode] = useState('matrix')
  const [loading, setLoading] = useState(false)
  const [clusters, setClusters] = useState([])
  const [matrix, setMatrix] = useState({})
  const [stats, setStats] = useState(null)

  useEffect(() => {
    loadFunctionData()
  }, [])

  const loadFunctionData = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_ENDPOINTS.GRAPHS.FUNCTION_SIMILARITY}?view_mode=aggregate&top_n=20`)
      const data = await response.json()
      
      if (data.data && data.data.nodes) {
        setClusters(data.data.nodes)
        setStats(data.data.stats)
        
        const matrixData = buildConnectionMatrix(data.data.nodes, data.data.edges)
        setMatrix(matrixData)
      }
    } catch (error) {
      console.error('Error loading function analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  const buildConnectionMatrix = (nodes, edges) => {
    const functions = ['Communications', 'Earth Observation', 'Scientific Research', 'Navigation', 'Military-Defense', 'Space Station', 'Technology-Testing']
    const matrixData = {}
    
    functions.forEach(func1 => {
      matrixData[func1] = {}
      functions.forEach(func2 => {
        matrixData[func1][func2] = { count: 0, clusters: [] }
      })
    })
    
    edges.forEach(edge => {
      const sourceNode = nodes.find(n => n.id === edge.source)
      const targetNode = nodes.find(n => n.id === edge.target)
      
      if (sourceNode && targetNode) {
        const func1 = sourceNode.function
        const func2 = targetNode.function
        
        if (matrixData[func1] && matrixData[func1][func2]) {
          matrixData[func1][func2].count += edge.connection_count || 1
          matrixData[func1][func2].clusters.push({ source: sourceNode.id, target: targetNode.id })
        }
        
        if (matrixData[func2] && matrixData[func2][func1]) {
          matrixData[func2][func1].count += edge.connection_count || 1
          matrixData[func2][func1].clusters.push({ source: targetNode.id, target: sourceNode.id })
        }
      }
    })
    
    return matrixData
  }

  const getColor = (count) => {
    if (count === 0) return '#f5f5f5'
    if (count < 10) return '#e3f2fd'
    if (count < 50) return '#90caf9'
    if (count < 100) return '#42a5f5'
    if (count < 500) return '#1976d2'
    return '#0d47a1'
  }

  const renderMatrix = () => {
    const functions = Object.keys(matrix)
    
    return (
      <div className="matrix-container">
        <h3>Function Relationship Matrix</h3>
        <p className="description">
          Shows connection strength between different satellite functions. Darker colors indicate more connections.
        </p>
        
        <div className="matrix-wrapper">
          <table className="connection-matrix">
            <thead>
              <tr>
                <th></th>
                {functions.map(func => (
                  <th key={func} className="matrix-header">{func}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {functions.map(func1 => (
                <tr key={func1}>
                  <th className="matrix-row-header">{func1}</th>
                  {functions.map(func2 => {
                    const cell = matrix[func1]?.[func2] || { count: 0 }
                    const color = getColor(cell.count)
                    return (
                      <td
                        key={func2}
                        className="matrix-cell"
                        style={{ backgroundColor: color }}
                        title={`${func1} ↔ ${func2}: ${cell.count} connections`}
                      >
                        {cell.count > 0 ? cell.count : '-'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        <div className="legend">
          <h4>Legend</h4>
          <div className="legend-items">
            <div className="legend-item">
              <div className="legend-box" style={{ backgroundColor: '#f5f5f5' }}></div>
              <span>No connections</span>
            </div>
            <div className="legend-item">
              <div className="legend-box" style={{ backgroundColor: '#e3f2fd' }}></div>
              <span>1-9 connections</span>
            </div>
            <div className="legend-item">
              <div className="legend-box" style={{ backgroundColor: '#90caf9' }}></div>
              <span>10-49 connections</span>
            </div>
            <div className="legend-item">
              <div className="legend-box" style={{ backgroundColor: '#42a5f5' }}></div>
              <span>50-99 connections</span>
            </div>
            <div className="legend-item">
              <div className="legend-box" style={{ backgroundColor: '#1976d2' }}></div>
              <span>100-499 connections</span>
            </div>
            <div className="legend-item">
              <div className="legend-box" style={{ backgroundColor: '#0d47a1' }}></div>
              <span>500+ connections</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const renderStatistics = () => {
    const functionGroups = {}
    clusters.forEach(cluster => {
      if (!functionGroups[cluster.function]) {
        functionGroups[cluster.function] = {
          clusters: [],
          totalSatellites: 0,
          totalEdges: 0,
          orbitalBands: new Set()
        }
      }
      functionGroups[cluster.function].clusters.push(cluster)
      functionGroups[cluster.function].totalSatellites += cluster.satellite_count
      functionGroups[cluster.function].totalEdges += cluster.edge_count
      functionGroups[cluster.function].orbitalBands.add(cluster.orbital_band)
    })

    const sortedFunctions = Object.entries(functionGroups).sort((a, b) => b[1].totalSatellites - a[1].totalSatellites)

    return (
      <div className="statistics-container">
        <h3>Function Similarity Statistics</h3>
        <p className="description">
          Overview of satellite function categories, their sizes, and connectivity patterns.
        </p>

        {stats && (
          <div className="summary-cards">
            <div className="summary-card">
              <div className="card-value">{stats.total_satellites?.toLocaleString() || 'N/A'}</div>
              <div className="card-label">Satellites</div>
            </div>
            <div className="summary-card">
              <div className="card-value">{stats.cluster_count || 0}</div>
              <div className="card-label">Clusters</div>
            </div>
            <div className="summary-card">
              <div className="card-value">{stats.inter_cluster_edges || 0}</div>
              <div className="card-label">Inter-Cluster Edges</div>
            </div>
          </div>
        )}

        <div className="function-groups">
          {sortedFunctions.map(([funcName, data]) => (
            <div key={funcName} className="function-group">
              <h4 className="function-name">{funcName}</h4>
              <div className="function-stats">
                <div className="stat">
                  <span className="stat-label">Satellites:</span>
                  <span className="stat-value">{data.totalSatellites.toLocaleString()}</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Clusters:</span>
                  <span className="stat-value">{data.clusters.length}</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Total Edges:</span>
                  <span className="stat-value">{data.totalEdges.toLocaleString()}</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Orbital Bands:</span>
                  <span className="stat-value">{Array.from(data.orbitalBands).join(', ')}</span>
                </div>
              </div>

              <div className="cluster-table">
                <table>
                  <thead>
                    <tr>
                      <th>Orbital Band</th>
                      <th>Satellites</th>
                      <th>Edges</th>
                      <th>Density</th>
                      <th>Top Countries</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.clusters
                      .sort((a, b) => b.satellite_count - a.satellite_count)
                      .map(cluster => (
                        <tr key={cluster.id}>
                          <td>{cluster.orbital_band}</td>
                          <td>{cluster.satellite_count}</td>
                          <td>{cluster.edge_count}</td>
                          <td>{(cluster.density * 100).toFixed(2)}%</td>
                          <td>{cluster.top_countries?.slice(0, 3).join(', ') || 'N/A'}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="function-analytics">
      <div className="analytics-header">
        <h2>Function Similarity Analytics</h2>
        <div className="view-selector">
          <button
            className={viewMode === 'matrix' ? 'active' : ''}
            onClick={() => setViewMode('matrix')}
          >
            Matrix View
          </button>
          <button
            className={viewMode === 'statistics' ? 'active' : ''}
            onClick={() => setViewMode('statistics')}
          >
            Statistics View
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loading">Loading analytics data...</div>
      ) : (
        <div className="analytics-content">
          {viewMode === 'matrix' && renderMatrix()}
          {viewMode === 'statistics' && renderStatistics()}
        </div>
      )}
    </div>
  )
}

export default FunctionAnalytics

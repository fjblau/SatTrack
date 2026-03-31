import { useState, useEffect, useMemo } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import './ObservationGraphs.css'

const CHART_DIMENSIONS = {
  WIDTH: 1200,
  HEIGHT: 500,
  PADDING: { top: 40, right: 40, bottom: 80, left: 80 }
}

const MENU_ITEMS = [
  {
    id: 'health',
    label: 'Health Trends',
    desc: 'Average health scores over time'
  },
  {
    id: 'anomaly',
    label: 'Anomaly Analysis',
    desc: 'Distribution of detected anomalies'
  },
  {
    id: 'source',
    label: 'Source Statistics',
    desc: 'Observations by data source'
  },
  {
    id: 'aql',
    label: 'AQL Editor',
    desc: 'Custom analytics queries'
  }
]

export default function ObservationGraphs() {
  const [activeView, setActiveView] = useState('health')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [granularity, setGranularity] = useState('daily')
  const [anomalyBy, setAnomalyBy] = useState('status') // source or object_type or status (null)
  const [aqlQuery, setAqlQuery] = useState('FOR obs IN observations\n  SORT obs.observation_epoch DESC\n  LIMIT 10\n  RETURN obs')
  const [aqlResults, setAqlResults] = useState(null)
  const [aqlLoading, setAqlLoading] = useState(false)

  const SAMPLE_QUERIES = [
    {
      label: 'Recent Observations',
      query: 'FOR obs IN observations\n  SORT obs.observation_epoch DESC\n  LIMIT 10\n  RETURN obs'
    },
    {
      label: 'Anomalies by Country',
      query: 'FOR obs IN observations\n  FILTER obs.thermal.anomaly_flag == true\n  COLLECT country = obs.origin_country WITH COUNT INTO count\n  SORT count DESC\n  RETURN { country, count }'
    },
    {
      label: 'Avg Health by Source',
      query: 'FOR obs IN observations\n  FILTER obs.derived_health_score != null\n  COLLECT source = obs.source AGGREGATE avg_health = AVERAGE(obs.derived_health_score)\n  SORT avg_health DESC\n  RETURN { source, avg_health }'
    }
  ]

  useEffect(() => {
    if (activeView !== 'aql') {
      fetchData()
    }
  }, [activeView, granularity, anomalyBy])

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    setData(null)

    let url = ''
    switch (activeView) {
      case 'health':
        url = `${API_ENDPOINTS.OBSERVATION_ANALYTICS.HEALTH}?granularity=${granularity}`
        break
      case 'anomaly':
        url = `${API_ENDPOINTS.OBSERVATION_ANALYTICS.ANOMALIES}${anomalyBy !== 'status' ? `?by=${anomalyBy}` : ''}`
        break
      case 'source':
        url = API_ENDPOINTS.OBSERVATION_ANALYTICS.SOURCES
        break
      default:
        return
    }

    try {
      const response = await apiFetch(url)
      if (!response.ok) throw new Error(`Failed to fetch: ${response.statusText}`)
      const result = await response.json()
      setData(result)
    } catch (err) {
      console.error('Error fetching analytics data:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const runAql = async () => {
    setAqlLoading(true)
    setError(null)
    setAqlResults(null)

    try {
      const response = await apiFetch(API_ENDPOINTS.OBSERVATION_ANALYTICS.AQL, {
        method: 'POST',
        body: JSON.stringify({ query: aqlQuery })
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || 'Failed to execute AQL query')
      setAqlResults(result)
    } catch (err) {
      console.error('Error running AQL:', err)
      setError(err.message)
    } finally {
      setAqlLoading(false)
    }
  }

  const renderContent = () => {
    if (loading) {
      return (
        <div className="loading-container">
          <p>Loading analytics data...</p>
        </div>
      )
    }

    if (error && activeView !== 'aql') {
      return (
        <div className="error-container">
          <div>
            <h3>Error Loading Data</h3>
            <p>{error}</p>
            <button onClick={fetchData} className="run-button">Retry</button>
          </div>
        </div>
      )
    }

    switch (activeView) {
      case 'health':
        return renderHealthTrends()
      case 'anomaly':
        return renderAnomalyAnalysis()
      case 'source':
        return renderSourceStats()
      case 'aql':
        return renderAqlEditor()
      default:
        return null
    }
  }

  const renderHealthTrends = () => {
    if (!data || data.length === 0) return <div className="no-results">No health data available</div>

    const { WIDTH: width, HEIGHT: height, PADDING: padding } = CHART_DIMENSIONS
    const chartWidth = width - padding.left - padding.right
    const chartHeight = height - padding.top - padding.bottom

    const minScore = 0
    const maxScore = 100
    
    const xScale = (index) => padding.left + (index / (data.length - 1)) * chartWidth
    const yScale = (score) => padding.top + chartHeight - (score / maxScore) * chartHeight

    const pathData = data.map((d, i) => {
      const x = xScale(i)
      const y = yScale(d.average_health_score)
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
    }).join(' ')

    const areaData = `M ${xScale(0)} ${padding.top + chartHeight} ${pathData} L ${xScale(data.length - 1)} ${padding.top + chartHeight} Z`

    return (
      <div className="chart-card">
        <h2>Health Trends</h2>
        <p className="chart-description">Average satellite health score over time</p>
        
        <div className="chart-controls">
          <label>Granularity:</label>
          <select value={granularity} onChange={(e) => setGranularity(e.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </div>

        <svg width={width} height={height} className="observation-chart">
          <defs>
            <linearGradient id="chartGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#3498db" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#3498db" stopOpacity="0.05" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 20, 40, 60, 80, 100].map(v => (
            <g key={v}>
              <line 
                x1={padding.left} 
                y1={yScale(v)} 
                x2={padding.left + chartWidth} 
                y2={yScale(v)} 
                className="grid-line" 
              />
              <text x={padding.left - 10} y={yScale(v)} textAnchor="end" alignmentBaseline="middle" className="axis-text">
                {v}
              </text>
            </g>
          ))}

          {/* X axis labels (sample some) */}
          {data.map((d, i) => {
            if (data.length > 10 && i % Math.ceil(data.length / 10) !== 0) return null
            return (
              <text 
                key={i} 
                x={xScale(i)} 
                y={padding.top + chartHeight + 35} 
                textAnchor="middle" 
                className="axis-text"
                transform={`rotate(-45, ${xScale(i)}, ${padding.top + chartHeight + 35})`}
              >
                {d.date}
              </text>
            )
          })}

          <path d={areaData} className="chart-area" />
          <path d={pathData} className="chart-path" />

          {data.map((d, i) => (
            <circle 
              key={i} 
              cx={xScale(i)} 
              cy={yScale(d.average_health_score)} 
              r="4" 
              className="chart-dot"
            >
              <title>{`${d.date}: ${d.average_health_score.toFixed(2)}`}</title>
            </circle>
          ))}

          <line 
            x1={padding.left} 
            y1={padding.top} 
            x2={padding.left} 
            y2={padding.top + chartHeight} 
            className="axis-line" 
          />
          <line 
            x1={padding.left} 
            y1={padding.top + chartHeight} 
            x2={padding.left + chartWidth} 
            y2={padding.top + chartHeight} 
            className="axis-line" 
          />

          <text 
            x={padding.left - 60} 
            y={padding.top + chartHeight / 2} 
            textAnchor="middle" 
            className="axis-label"
            transform={`rotate(-90, ${padding.left - 60}, ${padding.top + chartHeight / 2})`}
          >
            Health Score
          </text>
        </svg>
      </div>
    )
  }

  const renderAnomalyAnalysis = () => {
    if (!data || data.length === 0) return <div className="no-results">No anomaly data available</div>

    const { WIDTH: width, HEIGHT: height, PADDING: padding } = CHART_DIMENSIONS
    const chartWidth = width - padding.left - padding.right
    const chartHeight = height - padding.top - padding.bottom

    const maxVal = Math.max(...data.map(d => d.value))
    const barWidth = (chartWidth / data.length) * 0.7
    const gap = (chartWidth / data.length) * 0.3

    const yScale = (val) => padding.top + chartHeight - (val / maxVal) * chartHeight

    return (
      <div className="chart-card">
        <h2>Anomaly Analysis</h2>
        <p className="chart-description">Frequency of anomalies grouped by different categories</p>
        
        <div className="chart-controls">
          <label>Group By:</label>
          <select value={anomalyBy} onChange={(e) => setAnomalyBy(e.target.value)}>
            <option value="status">Presence (Overall)</option>
            <option value="source">Source</option>
            <option value="object_type">Object Type</option>
          </select>
        </div>

        <svg width={width} height={height} className="observation-chart">
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map(p => {
            const val = Math.round(p * maxVal)
            return (
              <g key={p}>
                <line 
                  x1={padding.left} 
                  y1={yScale(val)} 
                  x2={padding.left + chartWidth} 
                  y2={yScale(val)} 
                  className="grid-line" 
                />
                <text x={padding.left - 10} y={yScale(val)} textAnchor="end" alignmentBaseline="middle" className="axis-text">
                  {val}
                </text>
              </g>
            )
          })}

          {data.map((d, i) => {
            const x = padding.left + i * (barWidth + gap) + gap / 2
            const h = chartHeight - (yScale(d.value) - padding.top)
            return (
              <g key={i}>
                <rect 
                  x={x} 
                  y={yScale(d.value)} 
                  width={barWidth} 
                  height={h} 
                  className="bar" 
                >
                  <title>{`${d.label}: ${d.value}`}</title>
                </rect>
                <text 
                  x={x + barWidth / 2} 
                  y={padding.top + chartHeight + 20} 
                  textAnchor="middle" 
                  className="axis-text"
                >
                  {d.label}
                </text>
                <text 
                  x={x + barWidth / 2} 
                  y={yScale(d.value) - 10} 
                  textAnchor="middle" 
                  className="bar-label"
                >
                  {d.value}
                </text>
              </g>
            )
          })}

          <line 
            x1={padding.left} 
            y1={padding.top} 
            x2={padding.left} 
            y2={padding.top + chartHeight} 
            className="axis-line" 
          />
          <line 
            x1={padding.left} 
            y1={padding.top + chartHeight} 
            x2={padding.left + chartWidth} 
            y2={padding.top + chartHeight} 
            className="axis-line" 
          />

          <text 
            x={padding.left - 60} 
            y={padding.top + chartHeight / 2} 
            textAnchor="middle" 
            className="axis-label"
            transform={`rotate(-90, ${padding.left - 60}, ${padding.top + chartHeight / 2})`}
          >
            Anomaly Count
          </text>
        </svg>
      </div>
    )
  }

  const renderSourceStats = () => {
    if (!data || data.length === 0) return <div className="no-results">No source data available</div>

    const { WIDTH: width, HEIGHT: height, PADDING: padding } = CHART_DIMENSIONS
    const chartWidth = width - padding.left - padding.right
    const chartHeight = height - padding.top - padding.bottom

    const maxVal = Math.max(...data.map(d => d.value))
    const barWidth = (chartWidth / data.length) * 0.7
    const gap = (chartWidth / data.length) * 0.3

    const yScale = (val) => padding.top + chartHeight - (val / maxVal) * chartHeight

    return (
      <div className="chart-card">
        <h2>Source Statistics</h2>
        <p className="chart-description">Number of observations contributed by each data source</p>
        
        <svg width={width} height={height} className="observation-chart">
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map(p => {
            const val = Math.round(p * maxVal)
            return (
              <g key={p}>
                <line 
                  x1={padding.left} 
                  y1={yScale(val)} 
                  x2={padding.left + chartWidth} 
                  y2={yScale(val)} 
                  className="grid-line" 
                />
                <text x={padding.left - 10} y={yScale(val)} textAnchor="end" alignmentBaseline="middle" className="axis-text">
                  {val}
                </text>
              </g>
            )
          })}

          {data.map((d, i) => {
            const x = padding.left + i * (barWidth + gap) + gap / 2
            const h = chartHeight - (yScale(d.value) - padding.top)
            return (
              <g key={i}>
                <rect 
                  x={x} 
                  y={yScale(d.value)} 
                  width={barWidth} 
                  height={h} 
                  className="bar" 
                  style={{ fill: '#2ecc71' }}
                >
                  <title>{`${d.label}: ${d.value}`}</title>
                </rect>
                <text 
                  x={x + barWidth / 2} 
                  y={padding.top + chartHeight + 20} 
                  textAnchor="middle" 
                  className="axis-text"
                >
                  {d.label}
                </text>
                <text 
                  x={x + barWidth / 2} 
                  y={yScale(d.value) - 10} 
                  textAnchor="middle" 
                  className="bar-label"
                >
                  {d.value}
                </text>
              </g>
            )
          })}

          <line 
            x1={padding.left} 
            y1={padding.top} 
            x2={padding.left} 
            y2={padding.top + chartHeight} 
            className="axis-line" 
          />
          <line 
            x1={padding.left} 
            y1={padding.top + chartHeight} 
            x2={padding.left + chartWidth} 
            y2={padding.top + chartHeight} 
            className="axis-line" 
          />

          <text 
            x={padding.left - 60} 
            y={padding.top + chartHeight / 2} 
            textAnchor="middle" 
            className="axis-label"
            transform={`rotate(-90, ${padding.left - 60}, ${padding.top + chartHeight / 2})`}
          >
            Observation Count
          </text>
        </svg>
      </div>
    )
  }

  const renderAqlEditor = () => {
    // Collect all unique keys from all rows to ensure consistent column headers
    const allKeys = useMemo(() => {
      if (!aqlResults || !aqlResults.data || aqlResults.data.length === 0) return []
      
      // If the first result is not an object, just use a generic 'Result' header
      if (typeof aqlResults.data[0] !== 'object' || aqlResults.data[0] === null) {
        return ['Result']
      }

      const keys = new Set()
      aqlResults.data.forEach(row => {
        if (typeof row === 'object' && row !== null) {
          Object.keys(row).forEach(k => keys.add(k))
        }
      })
      return Array.from(keys)
    }, [aqlResults])

    return (
      <div className="chart-card">
        <h2>AQL Editor</h2>
        <p className="chart-description">Execute custom ArangoDB Query Language queries for deep analytics</p>
        
        <div className="aql-editor-container">
          <div className="sample-queries">
            <label>Sample Queries:</label>
            <div className="sample-chips">
              {SAMPLE_QUERIES.map((sq, i) => (
                <button 
                  key={i} 
                  className="sample-chip" 
                  onClick={() => setAqlQuery(sq.query)}
                >
                  {sq.label}
                </button>
              ))}
            </div>
          </div>

          <textarea 
            className="aql-textarea"
            value={aqlQuery}
            onChange={(e) => setAqlQuery(e.target.value)}
            spellCheck="false"
          />
          
          <div className="aql-actions">
            {error && <div className="aql-error">{error}</div>}
            <div className="aql-buttons">
              <button 
                className="clear-button"
                onClick={() => {
                  setAqlResults(null)
                  setError(null)
                }}
              >
                Clear Results
              </button>
              <button 
                className="run-button" 
                onClick={runAql}
                disabled={aqlLoading}
              >
                {aqlLoading ? 'Running...' : 'Run Query'}
              </button>
            </div>
          </div>

          {aqlResults && (
            <div className="results-container">
              <div className="results-summary">
                Found {aqlResults.count} results
              </div>
              <table className="results-table">
                <thead>
                  <tr>
                    {allKeys.map(key => (
                      <th key={key}>{key}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {aqlResults.data.map((row, i) => (
                    <tr key={i}>
                      {allKeys.map((key, j) => {
                        const val = (typeof row === 'object' && row !== null) ? row[key] : (key === 'Result' ? row : undefined)
                        return (
                          <td key={j}>
                            {val === undefined ? (
                              <em className="null-val">N/A</em>
                            ) : typeof val === 'object' && val !== null ? (
                              <pre className="json-val">{JSON.stringify(val, null, 2)}</pre>
                            ) : (
                              String(val)
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
              {aqlResults.data.length === 0 && (
                <div className="no-results">Query returned no results</div>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="observation-graphs-container">
      <aside className="observation-graphs-sidebar">
        <h3>Analytics</h3>
        <p className="section-description">Select a visualization view</p>
        
        <div className="observation-graphs-menu">
          {MENU_ITEMS.map(item => (
            <div 
              key={item.id}
              className={`menu-item ${activeView === item.id ? 'active' : ''}`}
              onClick={() => setActiveView(item.id)}
            >
              <span className="item-label">{item.label}</span>
              <span className="item-desc">{item.desc}</span>
            </div>
          ))}
        </div>
      </aside>
      
      <main className="observation-graphs-main">
        {renderContent()}
      </main>
    </div>
  )
}

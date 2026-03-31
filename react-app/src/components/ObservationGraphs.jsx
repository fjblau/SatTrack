import { useState, useEffect, useMemo } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import GraphViewer from './GraphViewer'
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
    id: 'network',
    label: 'Observation Network',
    desc: 'Graph view of satellite observations'
  },
  {
    id: 'source-network',
    label: 'Source Reliability',
    desc: 'Sources linked to satellites by observation quality'
  },
  {
    id: 'temporal',
    label: 'Temporal Chains',
    desc: 'Sequential observation timeline per satellite'
  },
  {
    id: 'anomaly-correlation',
    label: 'Anomaly Correlation',
    desc: 'Cross-satellite anomaly co-occurrence'
  },
  {
    id: 'aql',
    label: 'AQL Editor',
    desc: 'Custom analytics queries with export'
  }
]

export default function ObservationGraphs() {
  const [activeView, setActiveView] = useState('health')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [granularity, setGranularity] = useState('daily')
  const [anomalyBy, setAnomalyBy] = useState('status')
  const [aqlQuery, setAqlQuery] = useState('FOR obs IN observations\n  SORT obs.observation_epoch DESC\n  LIMIT 10\n  RETURN obs')
  const [aqlResults, setAqlResults] = useState(null)
  const [aqlLoading, setAqlLoading] = useState(false)
  const [noradId, setNoradId] = useState('')
  const [neighborhoodData, setNeighborhoodData] = useState(null)
  const [hoveredIndex, setHoveredIndex] = useState(null)
  const [viewAsGraph, setViewAsGraph] = useState(false)

  // New graph view states
  const [sourceNetworkData, setSourceNetworkData] = useState(null)
  const [temporalChainData, setTemporalChainData] = useState(null)
  const [temporalNoradId, setTemporalNoradId] = useState('')
  const [anomalyCorrData, setAnomalyCorrData] = useState(null)
  const [graphStats, setGraphStats] = useState(null)
  const [sourceMinObs, setSourceMinObs] = useState(5)
  const [exportingFormat, setExportingFormat] = useState(null)

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
    },
    {
      label: 'Observation Edge Stats',
      query: 'LET sat_edges = LENGTH(observation_satellite_edges)\nLET src_edges = LENGTH(observation_source_edges)\nLET temp_edges = LENGTH(observation_temporal_edges)\nLET corr_edges = LENGTH(observation_correlation_edges)\nRETURN { satellite_edges: sat_edges, source_edges: src_edges, temporal_edges: temp_edges, correlation_edges: corr_edges }'
    },
    {
      label: 'Source-Satellite Connections',
      query: 'FOR e IN observation_satellite_edges\n  LET obs = DOCUMENT(e._from)\n  LET sat = DOCUMENT(e._to)\n  COLLECT source = obs.source, sat_name = sat.canonical.name WITH COUNT INTO obs_count\n  SORT obs_count DESC\n  LIMIT 20\n  RETURN { source, satellite: sat_name, observations: obs_count }'
    },
    {
      label: 'Temporal Health Drift',
      query: 'FOR e IN observation_temporal_edges\n  FILTER e.health_delta != null\n  FILTER ABS(e.health_delta) > 10\n  LET from_obs = DOCUMENT(e._from)\n  LET to_obs = DOCUMENT(e._to)\n  SORT ABS(e.health_delta) DESC\n  LIMIT 20\n  RETURN { norad_id: e.norad_id, from_epoch: e.from_epoch, to_epoch: e.to_epoch, health_delta: e.health_delta, from_health: from_obs.derived_health_score, to_health: to_obs.derived_health_score }'
    }
  ]

  const GRAPH_SAMPLE_QUERIES = [
    {
      label: 'Satellite Neighborhood Graph',
      query: '// Returns Cytoscape-compatible graph — toggle to Graph view\nLET sat = FIRST(FOR s IN satellites FILTER s.canonical.norad_cat_id == 25544 LIMIT 1 RETURN s)\nLET obs = (FOR o IN observations FILTER o.norad_id == 25544 SORT o.observation_epoch DESC LIMIT 10 RETURN o)\nLET sources = (FOR o IN obs COLLECT src = o.source RETURN src)\nRETURN {\n  nodes: APPEND(\n    APPEND(\n      [{ data: { id: sat._id, label: sat.canonical.name || sat._key, type: "satellite", background_color: "#2ecc71", node_size: 45 } }],\n      obs[* RETURN { data: { id: CURRENT._id, label: SUBSTRING(CURRENT.observation_epoch, 0, 16), type: "observation", background_color: "#3498db", node_size: 30 } }]\n    ),\n    sources[* RETURN { data: { id: CONCAT("source/", CURRENT), label: CURRENT, type: "source", background_color: "#e67e22", node_size: 35 } }]\n  ),\n  edges: APPEND(\n    obs[* RETURN { data: { id: CONCAT("e_sat_", CURRENT._key), source: sat._id, target: CURRENT._id, relationship_type: "observed_by" } }],\n    obs[* RETURN { data: { id: CONCAT("e_src_", CURRENT._key), source: CURRENT._id, target: CONCAT("source/", CURRENT.source), relationship_type: "reported_by" } }]\n  )\n}'
    }
  ]

  useEffect(() => {
    if (activeView !== 'aql' && activeView !== 'network' && activeView !== 'source-network' && activeView !== 'temporal' && activeView !== 'anomaly-correlation') {
      fetchData()
    }
  }, [activeView, granularity, anomalyBy])

  useEffect(() => {
    if (activeView === 'network' && noradId) {
      fetchNeighborhoodData()
    }
  }, [activeView, noradId])

  // Load graph stats when switching to any graph view
  useEffect(() => {
    if (['source-network', 'temporal', 'anomaly-correlation'].includes(activeView) && !graphStats) {
      fetchGraphStats()
    }
  }, [activeView])

  const fetchGraphStats = async () => {
    try {
      const response = await apiFetch(API_ENDPOINTS.GRAPHS.OBSERVATION_GRAPH_STATS)
      if (response.ok) {
        const result = await response.json()
        setGraphStats(result.data)
      }
    } catch (err) {
      console.error('Error fetching graph stats:', err)
    }
  }

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

  const fetchNeighborhoodData = async () => {
    if (!noradId) return
    setLoading(true)
    setError(null)
    setNeighborhoodData(null)

    try {
      const response = await apiFetch(`${API_ENDPOINTS.GRAPHS.OBSERVATION_NEIGHBORHOOD}?satellite_id=${noradId}`)
      if (!response.ok) throw new Error(`Failed to fetch neighborhood: ${response.statusText}`)
      const result = await response.json()
      setNeighborhoodData(result.data)
    } catch (err) {
      console.error('Error fetching neighborhood data:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fetchSourceNetwork = async () => {
    setLoading(true)
    setError(null)
    setSourceNetworkData(null)

    try {
      const response = await apiFetch(`${API_ENDPOINTS.GRAPHS.OBSERVATION_SOURCE_NETWORK}?min_observations=${sourceMinObs}&limit=100`)
      if (!response.ok) throw new Error(`Failed to fetch source network: ${response.statusText}`)
      const result = await response.json()
      setSourceNetworkData(result.data)
    } catch (err) {
      console.error('Error fetching source network:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fetchTemporalChain = async () => {
    if (!temporalNoradId) return
    setLoading(true)
    setError(null)
    setTemporalChainData(null)

    try {
      const response = await apiFetch(`${API_ENDPOINTS.GRAPHS.OBSERVATION_TEMPORAL_CHAIN}?norad_id=${temporalNoradId}&limit=50`)
      if (!response.ok) throw new Error(`Failed to fetch temporal chain: ${response.statusText}`)
      const result = await response.json()
      setTemporalChainData(result.data)
    } catch (err) {
      console.error('Error fetching temporal chain:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fetchAnomalyCorrelation = async () => {
    setLoading(true)
    setError(null)
    setAnomalyCorrData(null)

    try {
      const response = await apiFetch(`${API_ENDPOINTS.GRAPHS.OBSERVATION_ANOMALY_CORRELATION}?limit=100`)
      if (!response.ok) throw new Error(`Failed to fetch anomaly correlation: ${response.statusText}`)
      const result = await response.json()
      setAnomalyCorrData(result.data)
    } catch (err) {
      console.error('Error fetching anomaly correlation:', err)
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
      if (!response.ok) {
        const detail = result.detail
        const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join('; ') : JSON.stringify(detail)
        throw new Error(msg || 'Failed to execute AQL query')
      }
      setAqlResults(result)
    } catch (err) {
      console.error('Error running AQL:', err)
      setError(err.message)
    } finally {
      setAqlLoading(false)
    }
  }

  const exportResults = async (format) => {
    setExportingFormat(format)
    try {
      const response = await apiFetch(API_ENDPOINTS.OBSERVATION_ANALYTICS.AQL, {
        method: 'POST',
        body: JSON.stringify({ query: aqlQuery, format })
      })

      if (!response.ok) {
        const errData = await response.json()
        const detail = errData.detail
        const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join('; ') : JSON.stringify(detail)
        throw new Error(msg || 'Export failed')
      }

      const blob = await response.blob()
      const ext = format === 'csv' ? 'csv' : 'json'
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `aql_export.${ext}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export error:', err)
      setError(err.message)
    } finally {
      setExportingFormat(null)
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
      case 'network':
        return renderObservationNetwork()
      case 'source-network':
        return renderSourceNetwork()
      case 'temporal':
        return renderTemporalChain()
      case 'anomaly-correlation':
        return renderAnomalyCorrelation()
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
            if (data.length > 15 && i % Math.ceil(data.length / 15) !== 0) return null
            return (
              <text
                key={i}
                x={xScale(i)}
                y={padding.top + chartHeight + 15}
                textAnchor="middle"
                className="axis-text"
              >
                {d.date.substring(5)}
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
              r={hoveredIndex === i ? 6 : 4}
              className="chart-dot"
              onMouseEnter={() => setHoveredIndex(i)}
              onMouseLeave={() => setHoveredIndex(null)}
            />
          ))}

          {/* Tooltip */}
          {hoveredIndex !== null && data[hoveredIndex] && (
            <g>
              <rect
                x={xScale(hoveredIndex) - 60}
                y={yScale(data[hoveredIndex].average_health_score) - 50}
                width="120"
                height="40"
                fill="rgba(44, 62, 80, 0.9)"
                rx="4"
              />
              <text
                x={xScale(hoveredIndex)}
                y={yScale(data[hoveredIndex].average_health_score) - 35}
                textAnchor="middle"
                fontSize="11"
                fill="white"
                fontWeight="600"
              >
                {data[hoveredIndex].date}
              </text>
              <text
                x={xScale(hoveredIndex)}
                y={yScale(data[hoveredIndex].average_health_score) - 20}
                textAnchor="middle"
                fontSize="11"
                fill="#3498db"
                fontWeight="bold"
              >
                Score: {data[hoveredIndex].average_health_score.toFixed(2)}
              </text>
            </g>
          )}

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
                  className="bar anomaly-bar"
                >
                  <title>{`${d.label}: ${d.value}`}</title>
                </rect>
                <text
                  x={x + barWidth / 2}
                  y={padding.top + chartHeight + 20}
                  textAnchor="middle"
                  className="axis-text bar-axis-label"
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
                  className="bar source-bar"
                >
                  <title>{`${d.label}: ${d.value}`}</title>
                </rect>
                <text
                  x={x + barWidth / 2}
                  y={padding.top + chartHeight + 20}
                  textAnchor="middle"
                  className="axis-text bar-axis-label"
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

  const renderObservationNetwork = () => {
    return (
      <div className="chart-card network-view">
        <h2>Observation Network</h2>
        <p className="chart-description">Visual representation of satellite observations and their sources</p>

        <div className="chart-controls">
          <div className="search-box">
            <label htmlFor="norad-search">NORAD ID:</label>
            <input
              id="norad-search"
              type="text"
              placeholder="Enter NORAD ID (e.g. 25544)"
              value={noradId}
              onChange={(e) => setNoradId(e.target.value)}
              className="norad-input"
              onKeyDown={(e) => {
                if (e.key === 'Enter') fetchNeighborhoodData()
              }}
            />
            <button
              onClick={fetchNeighborhoodData}
              className="run-button"
              disabled={loading || !noradId}
            >
              Search
            </button>
          </div>
        </div>

        <div className="graph-container-wrapper">
          {neighborhoodData ? (
            <div style={{ height: 'calc(100vh - 320px)', minHeight: '500px', border: '1px solid #eee', borderRadius: '4px', overflow: 'hidden' }}>
              <GraphViewer
                graphType="neighborhood"
                neighborhoodData={neighborhoodData}
              />
            </div>
          ) : (
            <div className="graph-placeholder" style={{ height: 'calc(100vh - 320px)', minHeight: '500px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8f9fa', borderRadius: '4px', color: '#999', fontStyle: 'italic' }}>
              {loading ? (
                <p>Loading network data...</p>
              ) : (
                <p>Enter a NORAD ID to visualize its observation network</p>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  const renderSourceNetwork = () => {
    return (
      <div className="chart-card network-view">
        <h2>Source Reliability Network</h2>
        <p className="chart-description">Data sources connected to satellites, weighted by observation count and average health score</p>

        {graphStats && (
          <div className="graph-stats-bar">
            <span>Satellite edges: <strong>{graphStats.satellite_edges || 0}</strong></span>
            <span>Source edges: <strong>{graphStats.source_edges || 0}</strong></span>
            <span>Sources: <strong>{graphStats.sources || 0}</strong></span>
          </div>
        )}

        <div className="chart-controls">
          <label>Min observations per link:</label>
          <input
            type="number"
            min="1"
            max="100"
            value={sourceMinObs}
            onChange={(e) => setSourceMinObs(parseInt(e.target.value) || 1)}
            className="norad-input"
            style={{ width: '80px' }}
          />
          <button onClick={fetchSourceNetwork} className="run-button" disabled={loading}>
            {loading ? 'Loading...' : 'Load Network'}
          </button>
        </div>

        <div className="graph-container-wrapper">
          {sourceNetworkData ? (
            <div style={{ height: 'calc(100vh - 320px)', minHeight: '500px', border: '1px solid #eee', borderRadius: '4px', overflow: 'hidden' }}>
              <GraphViewer
                graphType="neighborhood"
                neighborhoodData={sourceNetworkData}
              />
            </div>
          ) : (
            <div className="graph-placeholder" style={{ height: 'calc(100vh - 320px)', minHeight: '500px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8f9fa', borderRadius: '4px', color: '#999', fontStyle: 'italic' }}>
              <p>Click "Load Network" to visualize source-satellite relationships</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  const renderTemporalChain = () => {
    return (
      <div className="chart-card network-view">
        <h2>Temporal Observation Chain</h2>
        <p className="chart-description">Sequential observations of a satellite over time. Edge colors show health score changes (green = improving, red = degrading).</p>

        {graphStats && (
          <div className="graph-stats-bar">
            <span>Temporal edges: <strong>{graphStats.temporal_edges || 0}</strong></span>
            <span>Total observations: <strong>{graphStats.observations || 0}</strong></span>
          </div>
        )}

        <div className="chart-controls">
          <div className="search-box">
            <label htmlFor="temporal-norad">NORAD ID:</label>
            <input
              id="temporal-norad"
              type="text"
              placeholder="Enter NORAD ID (e.g. 25544)"
              value={temporalNoradId}
              onChange={(e) => setTemporalNoradId(e.target.value)}
              className="norad-input"
              onKeyDown={(e) => {
                if (e.key === 'Enter') fetchTemporalChain()
              }}
            />
            <button onClick={fetchTemporalChain} className="run-button" disabled={loading || !temporalNoradId}>
              {loading ? 'Loading...' : 'Load Chain'}
            </button>
          </div>
        </div>

        <div className="graph-container-wrapper">
          {temporalChainData ? (
            <div style={{ height: 'calc(100vh - 320px)', minHeight: '500px', border: '1px solid #eee', borderRadius: '4px', overflow: 'hidden' }}>
              <GraphViewer
                graphType="neighborhood"
                neighborhoodData={temporalChainData}
              />
            </div>
          ) : (
            <div className="graph-placeholder" style={{ height: 'calc(100vh - 320px)', minHeight: '500px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8f9fa', borderRadius: '4px', color: '#999', fontStyle: 'italic' }}>
              <p>Enter a NORAD ID to view its observation timeline as a graph</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  const renderAnomalyCorrelation = () => {
    return (
      <div className="chart-card network-view">
        <h2>Anomaly Correlation Network</h2>
        <p className="chart-description">Satellites linked by simultaneous thermal anomaly detections. Edge weight shows number of co-occurrences.</p>

        {graphStats && (
          <div className="graph-stats-bar">
            <span>Correlation edges: <strong>{graphStats.correlation_edges || 0}</strong></span>
            <span>Total observations: <strong>{graphStats.observations || 0}</strong></span>
          </div>
        )}

        <div className="chart-controls">
          <button onClick={fetchAnomalyCorrelation} className="run-button" disabled={loading}>
            {loading ? 'Loading...' : 'Load Correlation Network'}
          </button>
        </div>

        <div className="graph-container-wrapper">
          {anomalyCorrData ? (
            <div style={{ height: 'calc(100vh - 320px)', minHeight: '500px', border: '1px solid #eee', borderRadius: '4px', overflow: 'hidden' }}>
              <GraphViewer
                graphType="neighborhood"
                neighborhoodData={anomalyCorrData}
              />
            </div>
          ) : (
            <div className="graph-placeholder" style={{ height: 'calc(100vh - 320px)', minHeight: '500px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8f9fa', borderRadius: '4px', color: '#999', fontStyle: 'italic' }}>
              <p>Click "Load Correlation Network" to see cross-satellite anomaly patterns</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  // Detect if AQL results contain graph data (nodes and edges) — must be at top level for hooks rules
  const hasGraphData = useMemo(() => {
    if (!aqlResults || !aqlResults.data || aqlResults.data.length === 0) return false

    if (aqlResults.data.length === 1) {
      const item = aqlResults.data[0]
      return item && typeof item === 'object' && item.nodes && item.edges
    }

    return false
  }, [aqlResults])

  // Collect all unique keys from all AQL result rows
  const allKeys = useMemo(() => {
    if (!aqlResults || !aqlResults.data || aqlResults.data.length === 0) return []

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

  const renderAqlEditor = () => {
    return (
      <div className="chart-card">
        <div className="card-header-actions">
          <h2>AQL Editor</h2>
          <div className="header-controls">
            {hasGraphData && (
              <div className="view-toggle">
                <button
                  className={`toggle-btn ${!viewAsGraph ? 'active' : ''}`}
                  onClick={() => setViewAsGraph(false)}
                >
                  Table
                </button>
                <button
                  className={`toggle-btn ${viewAsGraph ? 'active' : ''}`}
                  onClick={() => setViewAsGraph(true)}
                >
                  Graph
                </button>
              </div>
            )}
          </div>
        </div>
        <p className="chart-description">Execute custom ArangoDB Query Language queries for deep analytics. Export results as CSV or JSON for data science workflows.</p>

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
              {GRAPH_SAMPLE_QUERIES.map((sq, i) => (
                <button
                  key={`graph-${i}`}
                  className="sample-chip challenge-chip"
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
                  setViewAsGraph(false)
                }}
              >
                Clear Results
              </button>
              <div className="export-buttons">
                <button
                  className="export-button"
                  onClick={() => exportResults('csv')}
                  disabled={aqlLoading || exportingFormat !== null}
                  title="Export results as CSV"
                >
                  {exportingFormat === 'csv' ? 'Exporting...' : 'Export CSV'}
                </button>
                <button
                  className="export-button"
                  onClick={() => exportResults('json_file')}
                  disabled={aqlLoading || exportingFormat !== null}
                  title="Export results as JSON"
                >
                  {exportingFormat === 'json_file' ? 'Exporting...' : 'Export JSON'}
                </button>
              </div>
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

              {viewAsGraph && hasGraphData ? (
                <div style={{ height: '500px', borderTop: '1px solid #eee' }}>
                  <GraphViewer
                    graphType="neighborhood"
                    neighborhoodData={aqlResults.data[0]}
                  />
                </div>
              ) : (
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
                                <div className="json-wrapper">
                                  <pre className="json-val">{JSON.stringify(val, null, 2)}</pre>
                                  <button
                                    className="copy-val-btn"
                                    onClick={() => navigator.clipboard.writeText(JSON.stringify(val, null, 2))}
                                    title="Copy JSON"
                                  >
                                    Copy
                                  </button>
                                </div>
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
              )}
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

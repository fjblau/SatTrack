import { useState, useMemo } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import GraphViewer from './GraphViewer'
import './ObservationGraphs.css'

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
  },
  {
    label: 'Satellite Catalog Stats',
    query: 'LET total = LENGTH(satellites)\nLET by_status = (\n  FOR s IN satellites\n    COLLECT status = s.canonical.status WITH COUNT INTO cnt\n    SORT cnt DESC\n    RETURN { status, count: cnt }\n)\nLET by_band = (\n  FOR s IN satellites\n    COLLECT band = s.canonical.orbital_band WITH COUNT INTO cnt\n    SORT cnt DESC\n    RETURN { band, count: cnt }\n)\nRETURN { total_satellites: total, by_status, by_orbital_band: by_band }'
  },
  {
    label: 'Graph Traversal Example',
    query: '// Traverse constellation membership edges from a satellite\nFOR v, e, p IN 1..2 ANY "satellites/2023-155H" constellation_membership\n  LIMIT 20\n  RETURN { vertex: v.canonical.name || v._key, edge_type: e._id }'
  }
]

const GRAPH_SAMPLE_QUERIES = [
  {
    label: 'Satellite Neighborhood Graph',
    query: '// Returns Cytoscape-compatible graph \u2014 toggle to Graph view\nLET sat = FIRST(FOR s IN satellites FILTER s.canonical.norad_cat_id == 25544 LIMIT 1 RETURN s)\nLET obs = (FOR o IN observations FILTER o.norad_id == 25544 SORT o.observation_epoch DESC LIMIT 10 RETURN o)\nLET sources = (FOR o IN obs COLLECT src = o.source RETURN src)\nRETURN {\n  nodes: APPEND(\n    APPEND(\n      [{ data: { id: sat._id, label: sat.canonical.name || sat._key, type: "satellite", background_color: "#2ecc71", node_size: 45 } }],\n      obs[* RETURN { data: { id: CURRENT._id, label: SUBSTRING(CURRENT.observation_epoch, 0, 16), type: "observation", background_color: "#3498db", node_size: 30 } }]\n    ),\n    sources[* RETURN { data: { id: CONCAT("source/", CURRENT), label: CURRENT, type: "source", background_color: "#e67e22", node_size: 35 } }]\n  ),\n  edges: APPEND(\n    obs[* RETURN { data: { id: CONCAT("e_sat_", CURRENT._key), source: sat._id, target: CURRENT._id, relationship_type: "observed_by" } }],\n    obs[* RETURN { data: { id: CONCAT("e_src_", CURRENT._key), source: CURRENT._id, target: CONCAT("source/", CURRENT.source), relationship_type: "reported_by" } }]\n  )\n}'
  }
]

export default function AqlEditorPage() {
  const [aqlQuery, setAqlQuery] = useState('FOR obs IN observations\n  SORT obs.observation_epoch DESC\n  LIMIT 10\n  RETURN obs')
  const [aqlResults, setAqlResults] = useState(null)
  const [aqlLoading, setAqlLoading] = useState(false)
  const [error, setError] = useState(null)
  const [viewAsGraph, setViewAsGraph] = useState(false)
  const [exportingFormat, setExportingFormat] = useState(null)

  const hasGraphData = useMemo(() => {
    if (!aqlResults || !aqlResults.data || aqlResults.data.length === 0) return false
    if (aqlResults.data.length === 1) {
      const item = aqlResults.data[0]
      return item && typeof item === 'object' && item.nodes && item.edges
    }
    return false
  }, [aqlResults])

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

  const runAql = async () => {
    setAqlLoading(true)
    setError(null)
    setAqlResults(null)

    try {
      const response = await apiFetch(API_ENDPOINTS.OBSERVATION_ANALYTICS.AQL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
        headers: { 'Content-Type': 'application/json' },
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
      setError(err.message)
    } finally {
      setExportingFormat(null)
    }
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '1600px', margin: '0 auto' }}>
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
        <p className="chart-description">Execute custom ArangoDB Query Language queries against the full database. Export results as CSV or JSON for data science workflows.</p>

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
            style={{ minHeight: '200px' }}
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
            <div className="results-container" style={{ maxHeight: 'calc(100vh - 550px)' }}>
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
    </div>
  )
}

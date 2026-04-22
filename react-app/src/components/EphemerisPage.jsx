import { useState, useEffect, useRef, useCallback } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import CesiumViewer from './CesiumViewer'
import './EphemerisPage.css'

const STEP_OPTIONS = [
  { label: '10 s', value: 10 },
  { label: '30 s', value: 30 },
  { label: '60 s', value: 60 },
  { label: '2 min', value: 120 },
  { label: '5 min', value: 300 },
  { label: '10 min', value: 600 },
]

const DURATION_OPTIONS = [
  { label: '6 h', value: 6 },
  { label: '12 h', value: 12 },
  { label: '24 h', value: 24 },
  { label: '3 days', value: 72 },
  { label: '7 days', value: 168 },
]

const PROPAGATOR_OPTIONS = [
  { label: 'SGP4 (fast)', value: 'SGP4' },
  { label: 'HIFI — GMAT RK89 + EGM96', value: 'HIFI' },
]

export default function EphemerisPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [selectedSatellite, setSelectedSatellite] = useState(null)

  const [stepSeconds, setStepSeconds] = useState(60)
  const [durationHours, setDurationHours] = useState(24)
  const [propagator, setPropagator] = useState('SGP4')
  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState(null)

  const [envelopes, setEnvelopes] = useState([])
  const [envelopesTotal, setEnvelopesTotal] = useState(0)
  const [envelopesLoading, setEnvelopesLoading] = useState(false)
  const [filterNoradId, setFilterNoradId] = useState(null)

  const [selectedEnvelope, setSelectedEnvelope] = useState(null)
  const [envelopeDetail, setEnvelopeDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailView, setDetailView] = useState('table')

  const [showEci, setShowEci] = useState(false)
  const searchDebounce = useRef(null)

  const fetchEnvelopes = useCallback(async (noradId = null) => {
    setEnvelopesLoading(true)
    try {
      const params = new URLSearchParams({ limit: 50, offset: 0 })
      if (noradId != null) params.append('norad_id', noradId)
      const res = await apiFetch(`${API_ENDPOINTS.EPHEMERIS.LIST}?${params}`)
      if (res.ok) {
        const data = await res.json()
        setEnvelopes(data.data || [])
        setEnvelopesTotal(data.total || 0)
      }
    } catch (err) {
      console.error('Error fetching ephemeris envelopes:', err)
    } finally {
      setEnvelopesLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchEnvelopes(filterNoradId)
  }, [filterNoradId, fetchEnvelopes])

  const handleSearchChange = (e) => {
    const q = e.target.value
    setSearchQuery(q)
    if (searchDebounce.current) clearTimeout(searchDebounce.current)
    if (!q.trim()) {
      setSearchResults([])
      return
    }
    searchDebounce.current = setTimeout(async () => {
      setSearchLoading(true)
      try {
        const params = new URLSearchParams({ q, limit: 10 })
        const res = await apiFetch(`${API_ENDPOINTS.SEARCH}?${params}`)
        if (res.ok) {
          const data = await res.json()
          setSearchResults(data.data || [])
        }
      } catch (err) {
        console.error('Search error:', err)
      } finally {
        setSearchLoading(false)
      }
    }, 300)
  }

  const handleSelectSatellite = (sat) => {
    const canonical = sat.canonical || {}
    setSelectedSatellite({
      name: canonical.object_name || canonical.name || sat.identifier || 'Unknown',
      norad_id: canonical.norad_cat_id,
      intl_des: canonical.international_designator,
    })
    setSearchQuery(canonical.object_name || canonical.name || sat.identifier || '')
    setSearchResults([])
  }

  const handleGenerate = async () => {
    if (!selectedSatellite?.norad_id) {
      setGenerateError('Selected satellite has no NORAD ID')
      return
    }
    setGenerating(true)
    setGenerateError(null)
    try {
      const res = await apiFetch(API_ENDPOINTS.EPHEMERIS.GENERATE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          norad_id: selectedSatellite.norad_id,
          duration_hours: durationHours,
          step_seconds: stepSeconds,
          propagator,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      await fetchEnvelopes(filterNoradId)
    } catch (err) {
      setGenerateError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  const handleSelectEnvelope = async (env) => {
    setSelectedEnvelope(env)
    setEnvelopeDetail(null)
    setDetailLoading(true)
    setDetailView('table')
    try {
      const id = env._key || env._id
      const res = await apiFetch(API_ENDPOINTS.EPHEMERIS.GET(id))
      if (res.ok) {
        setEnvelopeDetail(await res.json())
      }
    } catch (err) {
      console.error('Error fetching envelope detail:', err)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleDeleteEnvelope = async (env, e) => {
    e.stopPropagation()
    const id = env._key || env._id
    if (!window.confirm('Delete this ephemeris envelope?')) return
    try {
      await apiFetch(API_ENDPOINTS.EPHEMERIS.DELETE(id), { method: 'DELETE' })
      if (selectedEnvelope && (selectedEnvelope._key === env._key)) {
        setSelectedEnvelope(null)
        setEnvelopeDetail(null)
      }
      await fetchEnvelopes(filterNoradId)
    } catch (err) {
      console.error('Delete error:', err)
    }
  }

  const formatDt = (iso) => {
    if (!iso) return '—'
    return new Date(iso).toISOString().replace('T', ' ').substring(0, 19) + ' UTC'
  }

  const formatNum = (v, d = 2) => {
    if (v === null || v === undefined) return '—'
    return Number(v).toFixed(d)
  }

  return (
    <div className="ephemeris-page">
      <aside className="ephemeris-sidebar">
        <section className="eph-section">
          <h3>Generate Ephemeris</h3>

          <div className="eph-field">
            <label>Satellite</label>
            <div className="eph-search-wrapper">
              <input
                type="text"
                placeholder="Search by name or NORAD ID…"
                value={searchQuery}
                onChange={handleSearchChange}
                className="eph-input"
              />
              {searchLoading && <span className="eph-spinner" />}
              {searchResults.length > 0 && (
                <ul className="eph-search-results">
                  {searchResults.map((sat) => {
                    const canonical = sat.canonical || {}
                    const name = canonical.object_name || canonical.name || sat.identifier
                    const norad = canonical.norad_cat_id
                    return (
                      <li key={sat.identifier} onClick={() => handleSelectSatellite(sat)}>
                        <span className="eph-result-name">{name}</span>
                        {norad && <span className="eph-result-norad">NORAD {norad}</span>}
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
            {selectedSatellite && (
              <div className="eph-selected-sat">
                <span>{selectedSatellite.name}</span>
                {selectedSatellite.norad_id && (
                  <span className="eph-norad-badge">NORAD {selectedSatellite.norad_id}</span>
                )}
              </div>
            )}
          </div>

          <div className="eph-field">
            <label>Duration</label>
            <select
              value={durationHours}
              onChange={(e) => setDurationHours(Number(e.target.value))}
              className="eph-select"
            >
              {DURATION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="eph-field">
            <label>Step size</label>
            <select
              value={stepSeconds}
              onChange={(e) => setStepSeconds(Number(e.target.value))}
              className="eph-select"
            >
              {STEP_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="eph-field">
            <label>Propagator</label>
            <select
              value={propagator}
              onChange={(e) => setPropagator(e.target.value)}
              className="eph-select"
            >
              {PROPAGATOR_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {generateError && <p className="eph-error">{generateError}</p>}

          <button
            className="eph-generate-btn"
            onClick={handleGenerate}
            disabled={generating || !selectedSatellite?.norad_id}
          >
            {generating ? 'Generating…' : 'Generate & Store'}
          </button>
        </section>

        <section className="eph-section">
          <div className="eph-list-header">
            <h3>Stored Envelopes</h3>
            <div className="eph-list-controls">
              <label>
                <input
                  type="checkbox"
                  checked={filterNoradId != null}
                  onChange={(e) => {
                    if (e.target.checked && selectedSatellite?.norad_id) {
                      setFilterNoradId(selectedSatellite.norad_id)
                    } else {
                      setFilterNoradId(null)
                    }
                  }}
                />
                {' '}Filter by selected satellite
              </label>
            </div>
          </div>

          {envelopesLoading && <p className="eph-loading">Loading…</p>}

          {!envelopesLoading && envelopes.length === 0 && (
            <p className="eph-empty">No envelopes stored yet.</p>
          )}

          <div className="eph-envelope-list">
            {envelopes.map((env) => {
              const id = env._key || env._id
              const isSelected = selectedEnvelope && (selectedEnvelope._key === env._key)
              return (
                <div
                  key={id}
                  className={`eph-envelope-item${isSelected ? ' selected' : ''}`}
                  onClick={() => handleSelectEnvelope(env)}
                >
                  <div className="eph-env-name">{env.satellite_name || `NORAD ${env.norad_id}`}</div>
                  <div className="eph-env-meta">
                    <span>NORAD {env.norad_id}</span>
                    <span>{env.step_seconds}s step</span>
                    <span>{env.num_points} pts</span>
                  </div>
                  <div className="eph-env-time">{formatDt(env.generated_at)}</div>
                  <button
                    className="eph-delete-btn"
                    onClick={(e) => handleDeleteEnvelope(env, e)}
                    title="Delete envelope"
                  >
                    ×
                  </button>
                </div>
              )
            })}
          </div>
          {envelopesTotal > 50 && (
            <p className="eph-total">{envelopesTotal} total envelopes</p>
          )}
        </section>
      </aside>

      <main className="ephemeris-main">
        {!selectedEnvelope && (
          <div className="eph-placeholder">
            <p>Select a stored ephemeris envelope to view its data, or generate a new one.</p>
          </div>
        )}

        {selectedEnvelope && (
          <div className="eph-detail">
            <div className="eph-detail-header">
              <div>
                <h2>{envelopeDetail?.satellite_name || selectedEnvelope.satellite_name || `NORAD ${selectedEnvelope.norad_id}`}</h2>
                <p className="eph-detail-subtitle">
                  NORAD {selectedEnvelope.norad_id} &mdash; Generated {formatDt(selectedEnvelope.generated_at)}
                </p>
              </div>
              <div className="eph-view-toggle">
                <button
                  className={detailView === 'table' ? 'active' : ''}
                  onClick={() => setDetailView('table')}
                >
                  Table
                </button>
                <button
                  className={detailView === 'globe' ? 'active' : ''}
                  onClick={() => setDetailView('globe')}
                >
                  3D Globe
                </button>
              </div>
            </div>

            {detailLoading && <p className="eph-loading">Loading envelope…</p>}

            {!detailLoading && envelopeDetail && (
              <>
                <div className="eph-summary-grid">
                  <div className="eph-summary-item">
                    <span className="eph-sum-label">Valid from</span>
                    <span className="eph-sum-value">{formatDt(envelopeDetail.valid_from)}</span>
                  </div>
                  <div className="eph-summary-item">
                    <span className="eph-sum-label">Valid until</span>
                    <span className="eph-sum-value">{formatDt(envelopeDetail.valid_until)}</span>
                  </div>
                  <div className="eph-summary-item">
                    <span className="eph-sum-label">TLE epoch</span>
                    <span className="eph-sum-value">{formatDt(envelopeDetail.source_tle_epoch)}</span>
                  </div>
                  <div className="eph-summary-item">
                    <span className="eph-sum-label">Step</span>
                    <span className="eph-sum-value">{envelopeDetail.step_seconds} s</span>
                  </div>
                  <div className="eph-summary-item">
                    <span className="eph-sum-label">Points</span>
                    <span className="eph-sum-value">{envelopeDetail.num_points}</span>
                  </div>
                  <div className="eph-summary-item">
                    <span className="eph-sum-label">Period</span>
                    <span className="eph-sum-value">{formatNum(envelopeDetail.orbital_period_minutes)} min</span>
                  </div>
                  <div className="eph-summary-item">
                    <span className="eph-sum-label">Propagator</span>
                    <span className="eph-sum-value">{envelopeDetail.propagator || 'SGP4'}</span>
                  </div>
                </div>

                {detailView === 'table' && (
                  <div className="eph-points-section">
                    <div className="eph-points-header">
                      <h3>Ephemeris Points</h3>
                      <label className="eph-eci-toggle">
                        <input
                          type="checkbox"
                          checked={showEci}
                          onChange={(e) => setShowEci(e.target.checked)}
                        />
                        {' '}Show ECI coordinates
                      </label>
                    </div>
                    <div className="eph-table-wrapper">
                      <table className="eph-table">
                        <thead>
                          <tr>
                            <th>Time (UTC)</th>
                            <th className="numeric">Lat (°)</th>
                            <th className="numeric">Lon (°)</th>
                            <th className="numeric">Alt (km)</th>
                            <th className="numeric">Age (min)</th>
                            {showEci && (
                              <>
                                <th className="numeric">ECI X (km)</th>
                                <th className="numeric">ECI Y (km)</th>
                                <th className="numeric">ECI Z (km)</th>
                              </>
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {(envelopeDetail.ephemeris_points || []).map((pt, i) => (
                            <tr key={i}>
                              <td className="eph-ts">{formatDt(pt.timestamp)}</td>
                              <td className="numeric">{formatNum(pt.geodetic?.latitude)}</td>
                              <td className="numeric">{formatNum(pt.geodetic?.longitude)}</td>
                              <td className="numeric">{formatNum(pt.geodetic?.altitude_km, 1)}</td>
                              <td className="numeric">{formatNum(pt.propagation_age_minutes, 1)}</td>
                              {showEci && (
                                <>
                                  <td className="numeric">{formatNum(pt.eci?.x_km)}</td>
                                  <td className="numeric">{formatNum(pt.eci?.y_km)}</td>
                                  <td className="numeric">{formatNum(pt.eci?.z_km)}</td>
                                </>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {detailView === 'globe' && (
                  <CesiumViewer
                    envelopeId={envelopeDetail._key || envelopeDetail._id}
                    satelliteName={envelopeDetail.satellite_name}
                  />
                )}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

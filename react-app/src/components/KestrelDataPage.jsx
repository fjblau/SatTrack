import { useState, useEffect, useMemo } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import { parseTLE, propagateOrbit, generateCZML, orbitalPeriod } from '../utils/orbitUtils'
import KestrelDataGlobe from './KestrelDataGlobe'
import './KestrelDataPage.css'

const MAX_GLOBE_SATS = 20

function healthClass(score) {
  if (score == null) return 'unknown'
  if (score >= 70) return 'good'
  if (score >= 40) return 'warning'
  return 'critical'
}

function healthLabel(score) {
  if (score == null) return 'N/A'
  return score.toFixed(1)
}

function formatFieldValue(v) {
  if (v == null || v === '' || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  if (typeof v === 'number') return v.toFixed(3)
  return String(v)
}

function groupObservationsBySat(obs) {
  const map = new Map()
  for (const o of obs) {
    const key = o.norad_id || o.object_name || 'unknown'
    if (!map.has(key)) {
      map.set(key, {
        key,
        norad_id: o.norad_id,
        object_name: o.object_name || o.source || `NORAD ${o.norad_id}`,
        object_type: o.object_type,
        origin_country: o.origin_country,
        observations: [],
        latest_health: null,
        latest_epoch: null,
        obs_count: 0,
      })
    }
    const entry = map.get(key)
    entry.observations.push(o)
    entry.obs_count++
    if (!entry.latest_epoch || o.observation_epoch > entry.latest_epoch) {
      entry.latest_epoch = o.observation_epoch
      entry.latest_health = o.derived_health_score
    }
  }
  return Array.from(map.values()).sort((a, b) => {
    const ah = a.latest_health ?? 50
    const bh = b.latest_health ?? 50
    return ah - bh
  })
}

function buildCZML(satellites, tleMap) {
  const now = new Date()
  const startIso = now.toISOString()

  const satEntries = []
  for (const sat of satellites) {
    const tle = tleMap[sat.norad_id]
    if (!tle) continue
    const els = parseTLE(tle.line1 || tle.tle_line1, tle.line2 || tle.tle_line2)
    if (!els) continue
    const period = orbitalPeriod(els.sma)
    const duration = period * 2
    const step = Math.max(30, period / 120)
    const points = propagateOrbit(els, duration, step)
    const score = sat.latest_health
    const color = score == null
      ? [139, 155, 180, 220]
      : score >= 70 ? [39, 174, 96, 255]
      : score >= 40 ? [243, 156, 18, 255]
      : [231, 76, 60, 255]

    satEntries.push({
      id: `sat-${sat.norad_id}`,
      label: sat.object_name,
      points,
      color,
      pointSize: 8,
      pathWidth: 1.5,
      trailTime: period,
      leadTime: 0,
      availStartSec: 0,
      availEndSec: duration,
    })
  }

  if (!satEntries.length) return null
  const maxDuration = satEntries.reduce((m, s) => Math.max(m, s.availEndSec || 0), 0) || 7200
  return generateCZML(satEntries, startIso, maxDuration)
}

export default function KestrelDataPage() {
  const [activeSubTab, setActiveSubTab] = useState('globe')
  const [obsLoading, setObsLoading] = useState(true)
  const [obsError, setObsError] = useState(null)
  const [satellites, setSatellites] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSatKey, setSelectedSatKey] = useState(null)
  const [tleMap, setTleMap] = useState({})
  const [tleLoading, setTleLoading] = useState(false)
  const [czmlData, setCzmlData] = useState(null)
  const [czmlBuilding, setCzmlBuilding] = useState(false)

  useEffect(() => {
    const fetchObs = async () => {
      setObsLoading(true)
      setObsError(null)
      try {
        const params = new URLSearchParams({ limit: 500, sort_by: 'observation_epoch', sort_order: 'DESC' })
        const res = await apiFetch(`${API_ENDPOINTS.OBSERVATIONS}?${params}`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        const records = data.data || data.observations || []
        const grouped = groupObservationsBySat(records)
        setSatellites(grouped)
      } catch (err) {
        setObsError(err.message)
      } finally {
        setObsLoading(false)
      }
    }
    fetchObs()
  }, [])

  useEffect(() => {
    const satsWithNorad = satellites.filter(s => s.norad_id).slice(0, MAX_GLOBE_SATS)
    if (!satsWithNorad.length) return

    const missing = satsWithNorad.filter(s => !tleMap[s.norad_id])
    if (!missing.length) return

    setTleLoading(true)
    Promise.all(
      missing.map(async (s) => {
        try {
          const res = await apiFetch(`${API_ENDPOINTS.TLE}/${s.norad_id}`)
          if (!res.ok) return null
          const data = await res.json()
          const tle = data.data
          if (!tle) return null
          return { norad_id: s.norad_id, tle }
        } catch {
          return null
        }
      })
    ).then(results => {
      const newMap = { ...tleMap }
      for (const r of results) {
        if (r) newMap[r.norad_id] = r.tle
      }
      setTleMap(newMap)
      setTleLoading(false)
    })
  }, [satellites])

  const buildGlobe = () => {
    const satsWithTle = satellites.filter(s => s.norad_id && tleMap[s.norad_id]).slice(0, MAX_GLOBE_SATS)
    if (!satsWithTle.length) return
    setCzmlBuilding(true)
    setTimeout(() => {
      const czml = buildCZML(satsWithTle, tleMap)
      setCzmlData(czml)
      setCzmlBuilding(false)
    }, 0)
  }

  const filteredSats = useMemo(() => {
    if (!searchQuery.trim()) return satellites
    const q = searchQuery.toLowerCase()
    return satellites.filter(s =>
      s.object_name?.toLowerCase().includes(q) ||
      s.origin_country?.toLowerCase().includes(q) ||
      String(s.norad_id).includes(q)
    )
  }, [satellites, searchQuery])

  const selectedSat = useMemo(() =>
    satellites.find(s => s.key === selectedSatKey) || null,
    [satellites, selectedSatKey]
  )

  const focusedGlobeId = selectedSat?.norad_id ? `sat-${selectedSat.norad_id}` : null

  const totalObs = satellites.reduce((s, sat) => s + sat.obs_count, 0)
  const criticalCount = satellites.filter(s => s.latest_health != null && s.latest_health < 40).length
  const satsWithTleCount = satellites.filter(s => tleMap[s.norad_id]).length

  return (
    <div className="kdp-page">
      <nav className="kdp-subnav">
        <button
          className={activeSubTab === 'globe' ? 'active' : ''}
          onClick={() => setActiveSubTab('globe')}
        >
          3D Globe View
        </button>
        <button
          className={activeSubTab === 'observations' ? 'active' : ''}
          onClick={() => setActiveSubTab('observations')}
        >
          Observation Log
        </button>
      </nav>

      <div className="kdp-body">
        <aside className="kdp-sidebar">
          <div className="kdp-sidebar-title">Observed Objects</div>

          <div className="kdp-stats-row">
            <div className="kdp-stat">
              <div className="kdp-stat-value">{satellites.length}</div>
              <div className="kdp-stat-label">Objects</div>
            </div>
            <div className="kdp-stat">
              <div className="kdp-stat-value">{totalObs}</div>
              <div className="kdp-stat-label">Observations</div>
            </div>
            <div className="kdp-stat">
              <div className="kdp-stat-value" style={{ color: criticalCount > 0 ? '#e74c3c' : '#27ae60' }}>
                {criticalCount}
              </div>
              <div className="kdp-stat-label">Critical</div>
            </div>
          </div>

          <input
            className="kdp-search"
            type="text"
            placeholder="Search object…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />

          {obsLoading && <div className="kdp-loading-text">Loading observations…</div>}
          {obsError && <div className="kdp-loading-text" style={{ color: '#e74c3c' }}>Error: {obsError}</div>}

          <div className="kdp-sat-list">
            {filteredSats.map(sat => {
              const hc = healthClass(sat.latest_health)
              const hasTle = !!tleMap[sat.norad_id]
              return (
                <div
                  key={sat.key}
                  className={`kdp-sat-item${selectedSatKey === sat.key ? ' selected' : ''}`}
                  onClick={() => setSelectedSatKey(sat.key === selectedSatKey ? null : sat.key)}
                >
                  <div className="kdp-sat-item-header">
                    <div className="kdp-sat-name" title={sat.object_name}>{sat.object_name}</div>
                    <span className={`kdp-health-badge ${hc}`}>{healthLabel(sat.latest_health)}</span>
                  </div>
                  <div className="kdp-sat-meta">
                    <span>{sat.obs_count} obs</span>
                    {sat.origin_country && <span>· {sat.origin_country}</span>}
                    {sat.norad_id && <span>· #{sat.norad_id}</span>}
                  </div>
                  {sat.norad_id && !hasTle && (
                    <div className="kdp-no-tle">No TLE available</div>
                  )}
                </div>
              )
            })}
          </div>
        </aside>

        <div className="kdp-main">
          {activeSubTab === 'globe' && (
            <>
              <div className="kdp-globe-toolbar">
                <span className="kdp-globe-toolbar-label">
                  {czmlData
                    ? `Rendering ${satsWithTleCount} satellite${satsWithTleCount !== 1 ? 's' : ''} — colored by health score`
                    : tleLoading
                      ? 'Fetching TLE data…'
                      : `${satsWithTleCount} objects with TLE data ready`}
                </span>
                <button
                  className="kdp-build-btn"
                  onClick={buildGlobe}
                  disabled={czmlBuilding || tleLoading || satsWithTleCount === 0}
                >
                  {czmlBuilding ? 'Building…' : czmlData ? 'Refresh Globe' : 'Launch Globe'}
                </button>
                {czmlData && focusedGlobeId && (
                  <span className="kdp-globe-toolbar-label">
                    Tracking: <span className="kdp-globe-toolbar-count">{selectedSat?.object_name}</span>
                  </span>
                )}
              </div>
              <div className="kdp-globe-area">
                <KestrelDataGlobe
                  czmlData={czmlData}
                  focusedSatId={focusedGlobeId}
                  emptyMessage={
                    tleLoading
                      ? 'Fetching TLE data for observed objects…'
                      : satsWithTleCount === 0 && !obsLoading
                        ? 'No TLE data available for observed objects. The database may not have TLE records for these satellites.'
                        : 'Click "Launch Globe" to visualise observed objects in 3D.'
                  }
                />
              </div>
            </>
          )}

          {activeSubTab === 'observations' && (
            <div className="kdp-timeline-area">
              <div className="kdp-timeline-title">
                {selectedSat
                  ? `Observations — ${selectedSat.object_name}`
                  : 'All Observation Records'}
              </div>
              {obsLoading && <div className="kdp-loading-text">Loading…</div>}
              {!obsLoading && (
                <div className="kdp-obs-cards">
                  {(selectedSat ? selectedSat.observations : satellites.flatMap(s => s.observations))
                    .slice(0, 200)
                    .map((obs, idx) => (
                      <ObservationCard key={obs._key || idx} obs={obs} />
                    ))}
                </div>
              )}
              {!obsLoading && satellites.length === 0 && (
                <div className="kdp-obs-empty">No observation data available.</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ObservationCard({ obs }) {
  const hc = healthClass(obs.derived_health_score)
  const epoch = obs.observation_epoch
    ? new Date(obs.observation_epoch).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
    : '—'

  const fields = [
    { label: 'Source', value: obs.source },
    { label: 'Object Type', value: obs.object_type },
    { label: 'Country', value: obs.origin_country },
    { label: 'Mass (kg)', value: obs.estimated_mass_kg },
    { label: 'Spin (rpm)', value: obs.spin_rate_rpm },
    { label: 'Health Score', value: obs.derived_health_score },
  ]

  const sections = [
    { label: 'Attitude', data: obs.attitude, fields: ['roll_deg', 'pitch_deg', 'yaw_deg', 'stability_flag'] },
    { label: 'Thermal', data: obs.thermal, fields: ['surface_temp_K', 'temp_variance_30d', 'anomaly_flag'] },
    { label: 'Material', data: obs.material_signature, fields: ['reflectivity_index', 'inferred_material', 'confidence'] },
    { label: 'Proximity', data: obs.proximity_state, fields: ['range_km', 'relative_velocity_ms'] },
    { label: 'Maneuver', data: obs.maneuver_indicator, fields: ['delta_v_residual_ms', 'confidence', 'flag'] },
    { label: 'Orbital Decay', data: obs.orbital_decay_indicator, fields: ['perigee_drift_km_per_day', 'estimated_perigee_km'] },
  ]

  return (
    <div className="kdp-obs-card">
      <div className="kdp-obs-card-header">
        <div className="kdp-obs-card-name">{obs.object_name || `NORAD ${obs.norad_id}`}</div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {obs.derived_health_score != null && (
            <span className={`kdp-health-badge ${hc}`}>{obs.derived_health_score.toFixed(1)}</span>
          )}
          <div className="kdp-obs-card-meta">{epoch}</div>
        </div>
      </div>
      <div className="kdp-obs-card-body">
        {fields.map(f => (
          f.value != null && (
            <div key={f.label} className="kdp-obs-field">
              <div className="kdp-obs-field-label">{f.label}</div>
              <div className="kdp-obs-field-value">{formatFieldValue(f.value)}</div>
            </div>
          )
        ))}
        {sections.map(sec =>
          sec.data
            ? sec.fields.map(fk => (
                sec.data[fk] != null && (
                  <div key={`${sec.label}-${fk}`} className="kdp-obs-field">
                    <div className="kdp-obs-field-label">{sec.label} · {fk.replace(/_/g, ' ')}</div>
                    <div className="kdp-obs-field-value">{formatFieldValue(sec.data[fk])}</div>
                  </div>
                )
              ))
            : null
        )}
      </div>
    </div>
  )
}

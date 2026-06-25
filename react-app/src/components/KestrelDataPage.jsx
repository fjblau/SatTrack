import { useState, useEffect, useMemo, useRef } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import { parseTLE, parseTLEEpoch, propagateOrbit, generateCZML, orbitalPeriod } from '../utils/orbitUtils'
import KestrelDataGlobe from './KestrelDataGlobe'
import KestrelDataDials from './KestrelDataDials'
import './KestrelDataPage.css'

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

const TWO_PI = 2 * Math.PI
const GM_LOCAL = 3.986004418e14

function scoreColor(score) {
  return score == null
    ? [139, 155, 180, 220]
    : score >= 70 ? [39, 174, 96, 255]
    : score >= 40 ? [243, 156, 18, 255]
    : [231, 76, 60, 255]
}

function buildSingleSatCZML(sat, tle, observations) {
  const line1 = tle.line1 || tle.tle_line1
  const line2 = tle.line2 || tle.tle_line2
  const els = parseTLE(line1, line2)
  if (!els) return null

  const period = orbitalPeriod(els.sma)
  const step = Math.max(30, period / 120)
  const satColor = scoreColor(sat.latest_health)

  const obsEpochMs = (observations || [])
    .map(o => o.observation_epoch ? new Date(o.observation_epoch).getTime() : null)
    .filter(t => t != null && !isNaN(t))

  if (obsEpochMs.length === 0) {
    const duration = period * 2
    const points = propagateOrbit(els, duration, step)
    const startIso = new Date().toISOString()
    return {
      czml: generateCZML([{
        id: `sat-${sat.norad_id}`, label: sat.object_name,
        points, color: satColor, pointSize: 12, pathWidth: 2,
        trailTime: period, leadTime: 0, availStartSec: 0, availEndSec: duration,
      }], startIso, duration),
      windowStart: startIso,
      windowEnd: new Date(Date.now() + duration * 1000).toISOString(),
      obsWindowStart: null,
      obsWindowEnd: null,
    }
  }

  const obsStartMs = Math.min(...obsEpochMs)
  const obsEndMs = Math.max(...obsEpochMs)
  const windowStartMs = obsStartMs - 24 * 3600 * 1000
  const windowEndMs = obsEndMs + 24 * 3600 * 1000
  const totalDuration = (windowEndMs - windowStartMs) / 1000
  const obsDuration = Math.max((obsEndMs - obsStartMs) / 1000, period)
  const obsOffsetSec = (obsStartMs - windowStartMs) / 1000
  const windowStartIso = new Date(windowStartMs).toISOString()
  const obsStartIso = new Date(obsStartMs).toISOString()
  const obsEndIso = new Date(obsEndMs).toISOString()

  const tleEpochMs = parseTLEEpoch(line1) || Date.now()
  const n = Math.sqrt(GM_LOCAL / Math.pow(els.sma, 3))
  const deltaToWindowStart = (windowStartMs - tleEpochMs) / 1000
  const MA_at_window_start = ((els.meanAnomaly0 + n * deltaToWindowStart) % TWO_PI + TWO_PI) % TWO_PI
  const elsAtWindowStart = { ...els, meanAnomaly0: MA_at_window_start }

  const MA_at_obs_start = ((MA_at_window_start + n * obsOffsetSec) % TWO_PI + TWO_PI) % TWO_PI
  const elsAtObsStart = { ...els, meanAnomaly0: MA_at_obs_start }

  const fullPoints = propagateOrbit(elsAtWindowStart, totalDuration, step)
  const obsPointsRaw = propagateOrbit(elsAtObsStart, obsDuration, step)
  const obsPoints = obsPointsRaw.map(pt => ({ ...pt, t: pt.t + obsOffsetSec }))

  const LARGE_TIME = totalDuration * 4

  const czml = generateCZML([
    {
      id: 'sat-full-gray',
      label: '',
      noLabel: true,
      noPoint: true,
      points: fullPoints,
      color: [140, 160, 180, 90],
      pathWidth: 2,
      trailTime: LARGE_TIME,
      leadTime: LARGE_TIME,
      availStartSec: 0,
      availEndSec: totalDuration,
    },
    {
      id: 'sat-obs-highlight',
      label: '',
      noLabel: true,
      noPoint: true,
      points: obsPoints,
      color: [255, 160, 40, 220],
      pathWidth: 3,
      trailTime: LARGE_TIME,
      leadTime: LARGE_TIME,
      availStartSec: 0,
      availEndSec: totalDuration,
    },
    {
      id: `sat-${sat.norad_id}`,
      label: sat.object_name,
      points: fullPoints,
      color: satColor,
      pointSize: 12,
      pathWidth: 2,
      trailTime: period,
      leadTime: 0,
      availStartSec: 0,
      availEndSec: totalDuration,
    },
  ], windowStartIso, totalDuration, 300)

  return { czml, windowStart: windowStartIso, windowEnd: new Date(windowEndMs).toISOString(), obsWindowStart: obsStartIso, obsWindowEnd: obsEndIso }
}

export default function KestrelDataPage({ allowedSubtabs }) {
  const [activeSubTab, setActiveSubTab] = useState('globe')

  const isSubtabAllowed = (id) => !allowedSubtabs || allowedSubtabs.includes(id)
  const [obsLoading, setObsLoading] = useState(true)
  const [obsError, setObsError] = useState(null)
  const [satellites, setSatellites] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSatKey, setSelectedSatKey] = useState(null)
  const [tleCache, setTleCache] = useState({})
  const [tleFetching, setTleFetching] = useState(false)
  const [czmlData, setCzmlData] = useState(null)
  const [obsWindowStart, setObsWindowStart] = useState(null)
  const [obsWindowEnd, setObsWindowEnd] = useState(null)
  const [globeWindowStart, setGlobeWindowStart] = useState(null)
  const [globeWindowEnd, setGlobeWindowEnd] = useState(null)
  const [currentSimTime, setCurrentSimTime] = useState(null)
  const [analyticsHealth, setAnalyticsHealth] = useState(null)
  const [analyticsSummary, setAnalyticsSummary] = useState(null)
  const [analyticsLoading, setAnalyticsLoading] = useState(false)
  const analyticsAbortRef = useRef(null)

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
        setSatellites(groupObservationsBySat(records))
      } catch (err) {
        setObsError(err.message)
      } finally {
        setObsLoading(false)
      }
    }
    fetchObs()
  }, [])

  const selectedSat = useMemo(() =>
    satellites.find(s => s.key === selectedSatKey) || null,
    [satellites, selectedSatKey]
  )

  useEffect(() => {
    if (!selectedSat) {
      setCzmlData(null)
      setObsWindowStart(null)
      setObsWindowEnd(null)
      setGlobeWindowStart(null)
      setGlobeWindowEnd(null)
      setCurrentSimTime(null)
      return
    }
    const norad = selectedSat.norad_id
    if (!norad) {
      setCzmlData(null)
      setObsWindowStart(null)
      setObsWindowEnd(null)
      setGlobeWindowStart(null)
      setGlobeWindowEnd(null)
      return
    }

    const applyResult = (tle) => {
      const result = buildSingleSatCZML(selectedSat, tle, selectedSat.observations || [])
      if (!result) { setCzmlData(null); return }
      setCzmlData(result.czml)
      setObsWindowStart(result.obsWindowStart)
      setObsWindowEnd(result.obsWindowEnd)
      setGlobeWindowStart(result.windowStart)
      setGlobeWindowEnd(result.windowEnd)
    }

    if (tleCache[norad]) {
      applyResult(tleCache[norad])
      return
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 25000)

    setTleFetching(true)
    apiFetch(`${API_ENDPOINTS.TLE}/${norad}`, { signal: controller.signal })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        clearTimeout(timeoutId)
        const tle = data?.data
        if (!tle) { setCzmlData(null); return }
        setTleCache(prev => ({ ...prev, [norad]: tle }))
        applyResult(tle)
      })
      .catch(() => { clearTimeout(timeoutId); setCzmlData(null) })
      .finally(() => setTleFetching(false))

    return () => { controller.abort(); clearTimeout(timeoutId) }
  }, [selectedSat?.key])

  useEffect(() => {
    if (analyticsAbortRef.current) {
      analyticsAbortRef.current.abort()
      analyticsAbortRef.current = null
    }

    const norad = selectedSat?.norad_id
    if (!norad) {
      setAnalyticsHealth(null)
      setAnalyticsSummary(null)
      return
    }

    const controller = new AbortController()
    analyticsAbortRef.current = controller

    setAnalyticsLoading(true)
    setAnalyticsHealth(null)
    setAnalyticsSummary(null)

    Promise.all([
      apiFetch(API_ENDPOINTS.ANALYTICS.HEALTH(norad), { signal: controller.signal })
        .then(r => r.ok ? r.json() : null)
        .catch(() => null),
      apiFetch(API_ENDPOINTS.ANALYTICS.SUMMARY(norad), { signal: controller.signal })
        .then(r => r.ok ? r.json() : null)
        .catch(() => null),
    ]).then(([health, summary]) => {
      setAnalyticsHealth(health)
      setAnalyticsSummary(summary)
    }).finally(() => {
      setAnalyticsLoading(false)
    })

    return () => { controller.abort() }
  }, [selectedSat?.norad_id])

  const filteredSats = useMemo(() => {
    if (!searchQuery.trim()) return satellites
    const q = searchQuery.toLowerCase()
    return satellites.filter(s =>
      s.object_name?.toLowerCase().includes(q) ||
      s.origin_country?.toLowerCase().includes(q) ||
      String(s.norad_id).includes(q)
    )
  }, [satellites, searchQuery])

  const totalObs = satellites.reduce((s, sat) => s + sat.obs_count, 0)
  const criticalCount = satellites.filter(s => s.latest_health != null && s.latest_health < 40).length

  return (
    <div className="kdp-page">
      <nav className="kdp-subnav">
        {isSubtabAllowed('globe') && (
          <button
            className={activeSubTab === 'globe' ? 'active' : ''}
            onClick={() => setActiveSubTab('globe')}
          >
            3D Globe View
          </button>
        )}
        {isSubtabAllowed('observations') && (
          <button
            className={activeSubTab === 'observations' ? 'active' : ''}
            onClick={() => setActiveSubTab('observations')}
          >
            Observation Log
          </button>
        )}
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
              <div className="kdp-stat-label">Obs</div>
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
                  {!sat.norad_id && (
                    <div className="kdp-no-tle">No NORAD ID — 3D unavailable</div>
                  )}
                </div>
              )
            })}
          </div>
        </aside>

        <div className="kdp-main">
          {activeSubTab === 'globe' && (
            <div className="kdp-globe-area">
              <KestrelDataDials
                observations={selectedSat?.observations || []}
                satelliteName={selectedSat?.object_name}
                currentSimTime={currentSimTime}
                obsWindowStart={obsWindowStart}
                obsWindowEnd={obsWindowEnd}
                analyticsHealth={analyticsHealth}
                analyticsSummary={analyticsSummary}
                analyticsLoading={analyticsLoading}
              />
              <KestrelDataGlobe
                czmlData={czmlData}
                satelliteName={selectedSat?.object_name}
                healthScore={selectedSat?.latest_health}
                loading={tleFetching}
                windowStart={globeWindowStart}
                windowEnd={globeWindowEnd}
                obsWindowStart={obsWindowStart}
                obsWindowEnd={obsWindowEnd}
                onTimeChange={setCurrentSimTime}
                emptyMessage={
                  !selectedSat
                    ? 'Select an object from the list to view it in 3D.'
                    : !selectedSat.norad_id
                      ? 'No NORAD ID available — cannot render this object in 3D.'
                      : tleFetching
                        ? 'Fetching TLE data…'
                        : 'No TLE available for this object.'
                }
              />
            </div>
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
    { label: 'Material', data: obs.material_signature, fields: ['reflectivity_index', 'inferred_material', 'material_confidence'] },
    { label: 'Proximity', data: obs.proximity_state, fields: ['range_km', 'relative_velocity_ms'] },
    { label: 'Maneuver', data: obs.maneuver_indicator, fields: ['delta_v_residual_ms', 'maneuver_confidence', 'maneuver_flag'] },
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

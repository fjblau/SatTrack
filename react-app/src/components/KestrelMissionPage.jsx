import { useState, useRef, useCallback } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import KestrelCesiumViewer from './KestrelCesiumViewer'
import {
  propagateOrbit,
  propagateTransferOrbit,
  propagateScenarioArc,
  launchSiteToOrbitElements,
  altitudeToSMA,
  smaToAltitude,
  orbitalPeriod,
  parseTLE,
  hohmannTransfer,
  computeOptimalBurnWindow,
  computeManeuverScenarios,
  deorbitBurn,
  generateCZML,
  LAUNCH_SITES,
  ORBIT_PRESETS,
} from '../utils/orbitUtils'
import './KestrelMissionPage.css'

const RAD = 180 / Math.PI

function fmtDv(ms) {
  return (ms / 1000).toFixed(3) + ' km/s'
}

function fmtTime(seconds) {
  if (!isFinite(seconds)) return '∞'
  if (seconds < 3600) return (seconds / 60).toFixed(1) + ' min'
  if (seconds < 86400) return (seconds / 3600).toFixed(2) + ' h'
  return (seconds / 86400).toFixed(2) + ' days'
}

function fmtPeriod(seconds) {
  return (seconds / 60).toFixed(1) + ' min'
}

const MISSION_TYPES = [
  { id: 'observation', label: 'Observe',  icon: '👁',  desc: 'Proximity observation — characterize target state' },
  { id: 'inspection',  label: 'Inspect',  icon: '🔍', desc: 'Close-range inspection — material, tumble, shape' },
  { id: 'servicing',   label: 'Service',  icon: '🔧', desc: 'Active servicing — refuel, repair, extend life' },
  { id: 'deorbit',     label: 'Deorbit',  icon: '🔥', desc: 'ADR — capture and deorbit debris/dead satellite' },
]

export default function KestrelMissionPage() {
  const [activeSubTab, setActiveSubTab] = useState('launch')

  const [missionType, setMissionType] = useState('observation')

  const [targetQuery, setTargetQuery] = useState('')
  const [targetResults, setTargetResults] = useState([])
  const [targetSearching, setTargetSearching] = useState(false)
  const [selectedTarget, setSelectedTarget] = useState(null)
  const [targetElements, setTargetElements] = useState(null)
  const [targetFetchError, setTargetFetchError] = useState(null)
  const [targetFetchLoading, setTargetFetchLoading] = useState(false)
  const [targetTleSource, setTargetTleSource] = useState(null)

  const [launchSiteId, setLaunchSiteId] = useState('ksc')
  const [altitudeKm, setAltitudeKm] = useState(550)
  const [incDeg, setIncDeg] = useState(97.6)
  const [ecc, setEcc] = useState(0)

  const [kestrelCZML, setKestrelCZML] = useState(null)
  const [kestrelElements, setKestrelElements] = useState(null)
  const [computing, setComputing] = useState(false)
  const [computeError, setComputeError] = useState(null)

  const [maneuverResult, setManeuverResult] = useState(null)
  const [maneuverCZML, setManeuverCZML] = useState(null)
  const [scenarios, setScenarios] = useState(null)
  const [activeScenario, setActiveScenario] = useState(null)
  const [executedScenario, setExecutedScenario] = useState(null)

  const searchDebounce = useRef(null)
  const kestrelPointsRef = useRef(null)
  const targetPointsRef = useRef(null)
  const launchSite = LAUNCH_SITES.find((s) => s.id === launchSiteId) || LAUNCH_SITES[0]

  const applyPreset = (preset) => {
    setAltitudeKm(preset.altitudeKm)
    setIncDeg(preset.incDeg)
    setEcc(0)
  }

  const handleTargetSearch = (e) => {
    const q = e.target.value
    setTargetQuery(q)
    if (searchDebounce.current) clearTimeout(searchDebounce.current)
    if (!q.trim()) {
      setTargetResults([])
      return
    }
    searchDebounce.current = setTimeout(async () => {
      setTargetSearching(true)
      try {
        const params = new URLSearchParams({ q, limit: 10 })
        const res = await apiFetch(`${API_ENDPOINTS.SEARCH}?${params}`)
        if (res.ok) {
          const data = await res.json()
          setTargetResults(data.data || [])
        }
      } catch {
      } finally {
        setTargetSearching(false)
      }
    }, 300)
  }

  const handleSelectTarget = async (sat) => {
    const canonical = sat.canonical || {}
    const name = canonical.object_name || canonical.name || sat.identifier || 'Unknown'
    const noradId = canonical.norad_cat_id
    const objectType = canonical.object_type || ''
    setSelectedTarget({ name, noradId, objectType })
    setTargetQuery(name)
    setTargetResults([])
    setTargetElements(null)
    setTargetFetchError(null)
    setTargetTleSource(null)
    setManeuverResult(null)
    setManeuverCZML(null)

    if (!noradId) {
      setTargetFetchError('No NORAD ID — cannot fetch TLE.')
      return
    }

    setTargetFetchLoading(true)
    try {
      const res = await apiFetch(`${API_ENDPOINTS.TLE}/${noradId}`)
      if (!res.ok) throw new Error(`TLE fetch failed (HTTP ${res.status})`)
      const data = await res.json()
      const tle = data.data
      if (!tle) throw new Error('No TLE record found for this object. It may not yet have a TLE in the database.')
      const line1 = tle.line1 || tle.tle_line1
      const line2 = tle.line2 || tle.tle_line2
      if (!line1 || !line2) throw new Error('TLE lines missing in API response.')
      const els = parseTLE(line1, line2)
      if (!els) throw new Error('Failed to parse TLE data.')
      setTargetElements(els)
      setTargetTleSource(tle.source || data.source || 'celestrak')
      setIncDeg(parseFloat((els.inc * RAD).toFixed(1)))
      setAltitudeKm(Math.round(smaToAltitude(els.sma)))
    } catch (err) {
      setTargetFetchError(err.message)
    } finally {
      setTargetFetchLoading(false)
    }
  }

  const handlePlanMission = useCallback(() => {
    if (!selectedTarget) {
      setComputeError('Select a target object first.')
      return
    }
    setComputing(true)
    setComputeError(null)

    setTimeout(() => {
      try {
        const elements = launchSiteToOrbitElements(
          launchSite.lat,
          launchSite.lon,
          altitudeKm,
          incDeg,
          ecc
        )
        setKestrelElements(elements)

        const period = orbitalPeriod(elements.sma)
        const kestrelDuration = period * 3
        const kestrelStep = Math.max(10, Math.round(period / 240))
        const kestrelPoints = propagateOrbit(elements, kestrelDuration, kestrelStep)

        const startIso = new Date().toISOString()

        const launchCzml = generateCZML(
          [
            {
              id: 'kestrel',
              label: 'KESTREL',
              points: kestrelPoints,
              color: [52, 152, 219, 255],
              trailTime: period,
              leadTime: 0,
              pointSize: 12,
              pathWidth: 2.5,
            },
          ],
          startIso,
          kestrelDuration
        )
        setKestrelCZML(launchCzml)

        if (targetElements) {
          const r1 = elements.sma
          const r2 = targetElements.sma
          const transfer = hohmannTransfer(r1, r2)
          const burnWindow = computeOptimalBurnWindow(r1, r2)
          const incChangeDeg = Math.abs(elements.inc - targetElements.inc) * RAD
          const deorbit = missionType === 'deorbit' ? deorbitBurn(r2) : null

          setManeuverResult({
            ...transfer,
            ...burnWindow,
            kestrelAlt: smaToAltitude(r1).toFixed(1),
            targetAlt: smaToAltitude(r2).toFixed(1),
            incChangeDeg: incChangeDeg.toFixed(2),
            kestrelPeriod: period,
            targetPeriod: orbitalPeriod(r2),
            deorbit,
          })

          const targetPeriod = orbitalPeriod(r2)
          const targetStep = Math.max(10, Math.round(targetPeriod / 240))
          const targetPoints = propagateOrbit(targetElements, targetPeriod * 3, targetStep)

          kestrelPointsRef.current = { points: kestrelPoints, period, elements }
          targetPointsRef.current = { points: targetPoints, period: targetPeriod }

          const computed = computeManeuverScenarios(r1, r2)
          setScenarios(computed)
          setActiveScenario(null)
          setExecutedScenario(null)

          const defaultArc = propagateTransferOrbit(r1, r2, elements.raan, elements.inc, period * 2, 150)
          const totalDuration = kestrelDuration + transfer.transferTime + targetPeriod * 2
          setManeuverCZML(buildManeuverCZML(startIso, kestrelPoints, period, targetPoints, targetPeriod, defaultArc, transfer.transferTime, selectedTarget.name))
        }
      } catch (err) {
        setComputeError(err.message)
      } finally {
        setComputing(false)
      }
    }, 20)
  }, [launchSite, altitudeKm, incDeg, ecc, targetElements, selectedTarget, missionType])

  function buildManeuverCZML(startIso, kestrelPoints, kestrelPeriod, targetPoints, targetPeriod, arcPoints, arcDuration, targetName) {
    const sats = [
      {
        id: 'kestrel',
        label: 'KESTREL',
        points: kestrelPoints,
        color: [52, 152, 219, 255],
        trailTime: kestrelPeriod,
        leadTime: 0,
        pointSize: 12,
        pathWidth: 2.5,
      },
      {
        id: 'target',
        label: targetName || 'TARGET',
        points: targetPoints,
        color: [231, 76, 60, 255],
        trailTime: targetPeriod,
        leadTime: 0,
        pointSize: 10,
        pathWidth: 2,
      },
      {
        id: 'transfer',
        label: 'Transfer Arc',
        points: arcPoints,
        color: [241, 196, 15, 255],
        trailTime: arcDuration,
        leadTime: 0,
        pointSize: 6,
        pathWidth: 3,
      },
    ]
    const totalDuration = Math.max(
      kestrelPoints[kestrelPoints.length - 1]?.t || 0,
      targetPoints[targetPoints.length - 1]?.t || 0,
      arcPoints[arcPoints.length - 1]?.t || 0
    )
    return generateCZML(sats, startIso, totalDuration)
  }

  const handleExecuteScenario = useCallback((scenario) => {
    setExecutedScenario(scenario)
    const kp = kestrelPointsRef.current
    const tp = targetPointsRef.current
    if (!kp || !tp || !kestrelElements || !targetElements) return
    const arcPoints = propagateScenarioArc(scenario, kestrelElements, targetElements.sma, 150)
    const startIso = new Date().toISOString()
    const czml = buildManeuverCZML(
      startIso,
      kp.points,
      kp.period,
      tp.points,
      tp.period,
      arcPoints,
      scenario.transferTime,
      selectedTarget?.name
    )
    setManeuverCZML(czml)
  }, [kestrelElements, targetElements, selectedTarget])

  const kestrelPeriod = orbitalPeriod(altitudeToSMA(altitudeKm))
  const incWarning = Math.abs(launchSite.lat) > incDeg

  return (
    <div className="km-page">
      <div className="km-subnav">
        <button
          className={activeSubTab === 'launch' ? 'active' : ''}
          onClick={() => setActiveSubTab('launch')}
        >
          Launch Planner
        </button>
        <button
          className={activeSubTab === 'maneuver' ? 'active' : ''}
          onClick={() => setActiveSubTab('maneuver')}
          disabled={!kestrelElements}
          title={!kestrelElements ? 'Plan a mission first' : ''}
        >
          Maneuver Plan
          {maneuverResult && <span className="km-tab-badge">✓</span>}
        </button>
      </div>

      <div className="km-body">
        {activeSubTab === 'launch' && (
          <>
            <aside className="km-sidebar">

              <section className="km-section">
                <h3>1 — Mission Target</h3>
                <div className="km-field">
                  <div className="km-search-wrapper">
                    <input
                      type="text"
                      className="km-input"
                      placeholder="Search by name, NORAD ID, or type…"
                      value={targetQuery}
                      onChange={handleTargetSearch}
                    />
                    {(targetSearching || targetFetchLoading) && <span className="km-spinner" />}
                    {targetResults.length > 0 && (
                      <ul className="km-search-results">
                        {targetResults.map((sat) => {
                          const canonical = sat.canonical || {}
                          const name = canonical.object_name || canonical.name || sat.identifier
                          const norad = canonical.norad_cat_id
                          const type = canonical.object_type || ''
                          return (
                            <li key={sat.identifier} onClick={() => handleSelectTarget(sat)}>
                              <span className="km-res-name">{name}</span>
                              <div className="km-res-meta">
                                {norad && <span>NORAD {norad}</span>}
                                {type && <span className="km-res-type">{type}</span>}
                              </div>
                            </li>
                          )
                        })}
                      </ul>
                    )}
                  </div>
                </div>

                {targetFetchError && <p className="km-error">{targetFetchError}</p>}

                {selectedTarget && (
                  <div className="km-target-card">
                    <div className="km-target-name">{selectedTarget.name}</div>
                    <div className="km-target-meta">
                      {selectedTarget.noradId && (
                        <span className="km-badge">NORAD {selectedTarget.noradId}</span>
                      )}
                      {selectedTarget.objectType && (
                        <span className="km-badge km-badge-type">{selectedTarget.objectType}</span>
                      )}
                    </div>
                    {targetElements && (
                      <div className="km-orbit-summary km-target-orbit">
                        <div className="km-sum-item">
                          <span>Altitude</span>
                          <strong>{smaToAltitude(targetElements.sma).toFixed(0)} km</strong>
                        </div>
                        <div className="km-sum-item">
                          <span>Inclination</span>
                          <strong>{(targetElements.inc * RAD).toFixed(1)}°</strong>
                        </div>
                        <div className="km-sum-item">
                          <span>Period</span>
                          <strong>{fmtPeriod(orbitalPeriod(targetElements.sma))}</strong>
                        </div>
                        <div className="km-sum-item">
                          <span>Eccentricity</span>
                          <strong>{targetElements.ecc.toFixed(4)}</strong>
                        </div>
                      </div>
                    )}
                    {targetElements && (
                      <p className="km-hint-text km-hint-suggest">
                        ↑ Orbit parameters auto-matched to target
                        {targetTleSource === 'db_cached' && (
                          <span className="km-badge km-badge-cached" title="Live TLE unavailable — using last known TLE from database"> cached TLE</span>
                        )}
                      </p>
                    )}
                  </div>
                )}
              </section>

              <section className="km-section">
                <h3>2 — Mission Type</h3>
                <div className="km-mission-types">
                  {MISSION_TYPES.map((m) => (
                    <button
                      key={m.id}
                      className={`km-mission-btn${missionType === m.id ? ' active' : ''}`}
                      onClick={() => setMissionType(m.id)}
                      title={m.desc}
                    >
                      <span className="km-mission-icon">{m.icon}</span>
                      <span>{m.label}</span>
                    </button>
                  ))}
                </div>
                <p className="km-hint-text">
                  {MISSION_TYPES.find((m) => m.id === missionType)?.desc}
                </p>
              </section>

              <section className="km-section">
                <h3>3 — Launch Site</h3>
                <select
                  className="km-select"
                  value={launchSiteId}
                  onChange={(e) => setLaunchSiteId(e.target.value)}
                >
                  {LAUNCH_SITES.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} — {s.country}
                    </option>
                  ))}
                </select>
                <div className="km-site-info">
                  <span className="km-site-coord">
                    {launchSite.lat >= 0 ? launchSite.lat.toFixed(2) + '°N' : Math.abs(launchSite.lat).toFixed(2) + '°S'}
                    {' / '}
                    {launchSite.lon >= 0 ? launchSite.lon.toFixed(2) + '°E' : Math.abs(launchSite.lon).toFixed(2) + '°W'}
                  </span>
                  <span className="km-site-note">
                    Min reachable inclination: {Math.abs(launchSite.lat).toFixed(1)}°
                  </span>
                </div>
                {incWarning && (
                  <p className="km-warn-note">
                    ⚠ Inclination {incDeg.toFixed(1)}° &lt; site latitude {Math.abs(launchSite.lat).toFixed(1)}°. Choose a higher inclination or a different site.
                  </p>
                )}
              </section>

              <section className="km-section">
                <h3>4 — Orbit Parameters</h3>

                <div className="km-presets">
                  {ORBIT_PRESETS.map((p) => (
                    <button
                      key={p.id}
                      className="km-preset-btn"
                      onClick={() => applyPreset(p)}
                      title={p.description}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>

                <div className="km-field">
                  <label>
                    Altitude
                    <span className="km-field-value">{altitudeKm.toLocaleString()} km</span>
                  </label>
                  <input
                    type="range"
                    min={300}
                    max={36000}
                    step={10}
                    value={altitudeKm}
                    onChange={(e) => setAltitudeKm(Number(e.target.value))}
                    className="km-slider"
                  />
                  <div className="km-slider-labels">
                    <span>300 km</span>
                    <span>36 000 km</span>
                  </div>
                </div>

                <div className="km-field">
                  <label>
                    Inclination
                    <span className="km-field-value">{incDeg.toFixed(1)}°</span>
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={120}
                    step={0.1}
                    value={incDeg}
                    onChange={(e) => setIncDeg(Number(e.target.value))}
                    className="km-slider"
                  />
                  <div className="km-slider-labels">
                    <span>0° equatorial</span>
                    <span>90° polar</span>
                  </div>
                </div>

                <div className="km-field">
                  <label>
                    Eccentricity
                    <span className="km-field-value">{ecc.toFixed(3)}</span>
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={0.3}
                    step={0.001}
                    value={ecc}
                    onChange={(e) => setEcc(Number(e.target.value))}
                    className="km-slider"
                  />
                </div>

                <div className="km-orbit-summary">
                  <div className="km-sum-item">
                    <span>Period</span>
                    <strong>{fmtPeriod(kestrelPeriod)}</strong>
                  </div>
                  <div className="km-sum-item">
                    <span>SMA</span>
                    <strong>{(altitudeToSMA(altitudeKm) / 1000).toFixed(0)} km</strong>
                  </div>
                </div>

                {computeError && <p className="km-error">{computeError}</p>}

                <button
                  className="km-primary-btn"
                  onClick={handlePlanMission}
                  disabled={computing || !selectedTarget}
                >
                  {computing ? 'Computing…' : '🚀 Plan Mission'}
                </button>
                {!selectedTarget && (
                  <p className="km-hint-text" style={{ textAlign: 'center', marginTop: '4px' }}>
                    Select a target object above first
                  </p>
                )}
              </section>
            </aside>

            <KestrelCesiumViewer
              czmlData={kestrelCZML}
              launchSite={launchSite}
              emptyMessage="Select a target object, configure the launch orbit, then click Plan Mission."
            />
          </>
        )}

        {activeSubTab === 'maneuver' && (
          <>
            <aside className="km-sidebar">
              <section className="km-section">
                <h3>Mission Summary</h3>
                <div className="km-mission-summary-row">
                  <span className="km-sum-label">Target</span>
                  <span className="km-sum-value-inline">{selectedTarget?.name || '—'}</span>
                </div>
                <div className="km-mission-summary-row">
                  <span className="km-sum-label">Mission</span>
                  <span className="km-sum-value-inline">
                    {MISSION_TYPES.find((m) => m.id === missionType)?.icon}{' '}
                    {MISSION_TYPES.find((m) => m.id === missionType)?.label}
                  </span>
                </div>
                <div className="km-mission-summary-row">
                  <span className="km-sum-label">Launch site</span>
                  <span className="km-sum-value-inline">{launchSite.name}</span>
                </div>
              </section>

              {kestrelElements && (
                <section className="km-section">
                  <h3>Kestrel Parking Orbit</h3>
                  <div className="km-orbit-summary">
                    <div className="km-sum-item">
                      <span>Altitude</span>
                      <strong>{smaToAltitude(kestrelElements.sma).toFixed(0)} km</strong>
                    </div>
                    <div className="km-sum-item">
                      <span>Inclination</span>
                      <strong>{(kestrelElements.inc * RAD).toFixed(1)}°</strong>
                    </div>
                    <div className="km-sum-item">
                      <span>Period</span>
                      <strong>{fmtPeriod(orbitalPeriod(kestrelElements.sma))}</strong>
                    </div>
                    <div className="km-sum-item">
                      <span>RAAN</span>
                      <strong>{(kestrelElements.raan * RAD).toFixed(1)}°</strong>
                    </div>
                  </div>
                </section>
              )}

              {scenarios && (
                <section className="km-section">
                  <h3>Maneuver Scenarios</h3>
                  <p className="km-hint-text" style={{ marginBottom: '0.75rem' }}>
                    Select a scenario to preview, then execute to update the trajectory.
                  </p>
                  <div className="km-scenarios">
                    {scenarios.map((sc) => {
                      const isActive = activeScenario?.id === sc.id
                      const isExecuted = executedScenario?.id === sc.id
                      return (
                        <div
                          key={sc.id}
                          className={`km-scenario-card${isActive ? ' km-scenario-active' : ''}${isExecuted ? ' km-scenario-executed' : ''}`}
                        >
                          <div className="km-scenario-header">
                            <span className="km-scenario-name">{sc.name}</span>
                            <span className="km-scenario-tag" style={{ background: sc.tagColor + '33', color: sc.tagColor, borderColor: sc.tagColor }}>
                              {sc.tag}
                            </span>
                            {isExecuted && <span className="km-scenario-check">✓ ACTIVE</span>}
                          </div>
                          <p className="km-scenario-desc">{sc.desc}</p>
                          <div className="km-scenario-stats">
                            <div className="km-sc-stat">
                              <span>ΔV Total</span>
                              <strong style={{ color: sc.tagColor }}>{fmtDv(sc.dvTotal)}</strong>
                            </div>
                            <div className="km-sc-stat">
                              <span>Transfer</span>
                              <strong>{fmtTime(sc.transferTime)}</strong>
                            </div>
                            <div className="km-sc-stat">
                              <span>Wait</span>
                              <strong>{sc.waitTime === 0 ? 'None' : fmtTime(sc.waitTime)}</strong>
                            </div>
                          </div>
                          <div className="km-scenario-actions">
                            <button
                              className="km-btn-suggest"
                              onClick={() => setActiveScenario(isActive ? null : sc)}
                            >
                              {isActive ? 'Hide' : 'Preview'}
                            </button>
                            <button
                              className="km-btn-execute"
                              onClick={() => handleExecuteScenario(sc)}
                            >
                              {isExecuted ? '↺ Re-execute' : '▶ Execute'}
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  {activeScenario && !executedScenario && (
                    <div className="km-scenario-preview">
                      <div className="km-preview-title">Preview: {activeScenario.name}</div>
                      <div className="km-result-rows">
                        <div className="km-result-row"><span>ΔV₁ departure</span><strong className="km-dv">{fmtDv(activeScenario.dv1)}</strong></div>
                        <div className="km-result-row"><span>ΔV₂ arrival</span><strong className="km-dv">{fmtDv(activeScenario.dv2)}</strong></div>
                        <div className="km-result-row"><span>Transfer time</span><strong>{fmtTime(activeScenario.transferTime)}</strong></div>
                        <div className="km-result-row"><span>Phase wait</span><strong>{activeScenario.waitTime === 0 ? 'Immediate' : fmtTime(activeScenario.waitTime)}</strong></div>
                      </div>
                    </div>
                  )}
                </section>
              )}

              {maneuverResult && (
                <>
                  <section className="km-section km-results">
                    <h3>Transfer Plan</h3>

                    <div className="km-result-block">
                      <div className="km-result-title">Hohmann Transfer</div>
                      <div className="km-result-rows">
                        <div className="km-result-row">
                          <span>ΔV₁ — departure burn</span>
                          <strong className="km-dv">{fmtDv(maneuverResult.dv1)}</strong>
                        </div>
                        <div className="km-result-row">
                          <span>ΔV₂ — arrival burn</span>
                          <strong className="km-dv">{fmtDv(maneuverResult.dv2)}</strong>
                        </div>
                        <div className="km-result-row">
                          <span>Transfer time</span>
                          <strong>{fmtTime(maneuverResult.transferTime)}</strong>
                        </div>
                      </div>
                    </div>

                    {missionType === 'deorbit' && maneuverResult.deorbit && (
                      <div className="km-result-block km-deorbit-block">
                        <div className="km-result-title">🔥 Deorbit Burn (ADR)</div>
                        <div className="km-result-rows">
                          <div className="km-result-row">
                            <span>ΔV₃ — retrograde deorbit</span>
                            <strong className="km-dv">{fmtDv(maneuverResult.deorbit.dvDeorbit)}</strong>
                          </div>
                          <div className="km-result-row">
                            <span>Perigee after burn</span>
                            <strong>{maneuverResult.deorbit.altKm} km</strong>
                          </div>
                          <div className="km-result-row">
                            <span>Time to re-entry</span>
                            <strong>{fmtTime(maneuverResult.deorbit.deorbitTime)}</strong>
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="km-result-block">
                      <div className="km-result-title">ΔV Budget</div>
                      <div className="km-result-rows">
                        {missionType === 'deorbit' && maneuverResult.deorbit ? (
                          <>
                            <div className="km-result-row">
                              <span>Transfer (ΔV₁ + ΔV₂)</span>
                              <strong className="km-dv">{fmtDv(maneuverResult.dvTotal)}</strong>
                            </div>
                            <div className="km-result-row">
                              <span>Deorbit (ΔV₃)</span>
                              <strong className="km-dv">{fmtDv(maneuverResult.deorbit.dvDeorbit)}</strong>
                            </div>
                            <div className="km-result-row km-total">
                              <span>Total mission ΔV</span>
                              <strong className="km-dv">{fmtDv(maneuverResult.dvTotal + maneuverResult.deorbit.dvDeorbit)}</strong>
                            </div>
                          </>
                        ) : (
                          <div className="km-result-row km-total">
                            <span>Total ΔV</span>
                            <strong className="km-dv">{fmtDv(maneuverResult.dvTotal)}</strong>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="km-result-block">
                      <div className="km-result-title">Orbit Delta</div>
                      <div className="km-result-rows">
                        <div className="km-result-row">
                          <span>Altitude change</span>
                          <strong>
                            {parseFloat(maneuverResult.kestrelAlt).toFixed(0)} → {parseFloat(maneuverResult.targetAlt).toFixed(0)} km
                          </strong>
                        </div>
                        <div className="km-result-row">
                          <span>Inclination Δ</span>
                          <strong className={parseFloat(maneuverResult.incChangeDeg) > 5 ? 'km-warn' : ''}>
                            {maneuverResult.incChangeDeg}°
                            {parseFloat(maneuverResult.incChangeDeg) > 5 && ' ⚠'}
                          </strong>
                        </div>
                        <div className="km-result-row">
                          <span>Burn window (synodic)</span>
                          <strong>{fmtTime(maneuverResult.synodicPeriod)}</strong>
                        </div>
                      </div>
                      {parseFloat(maneuverResult.incChangeDeg) > 5 && (
                        <p className="km-warn-note">
                          Plane change required. Combined plane-change Hohmann will add approximately {((parseFloat(maneuverResult.incChangeDeg) * Math.PI / 180) * Math.sqrt(3.986e14 / altitudeToSMA(parseFloat(maneuverResult.targetAlt))) / 2).toFixed(3)} km/s.
                        </p>
                      )}
                    </div>
                  </section>
                </>
              )}

              {!maneuverResult && (
                <p className="km-hint-text" style={{ padding: '0.5rem 0' }}>
                  Plan a mission from the{' '}
                  <button className="km-link-btn" onClick={() => setActiveSubTab('launch')}>
                    Launch Planner
                  </button>{' '}
                  to see maneuver details.
                </p>
              )}
            </aside>

            <KestrelCesiumViewer
              czmlData={maneuverCZML}
              launchSite={null}
              targetLabel={selectedTarget?.name}
              emptyMessage="Complete the Launch Planner to see the full mission trajectory — Kestrel orbit (blue), target (red), transfer arc (yellow)."
            />
          </>
        )}
      </div>
    </div>
  )
}

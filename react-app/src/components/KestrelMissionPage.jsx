import { useState, useRef, useCallback } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import KestrelCesiumViewer from './KestrelCesiumViewer'
import {
  propagateOrbit,
  propagateTransferOrbit,
  altitudeToSMA,
  smaToAltitude,
  orbitalPeriod,
  parseTLE,
  hohmannTransfer,
  computeOptimalBurnWindow,
  generateCZML,
  LAUNCH_SITES,
  ORBIT_PRESETS,
} from '../utils/orbitUtils'
import './KestrelMissionPage.css'

const DEG = Math.PI / 180
const RAD = 180 / Math.PI

function fmtDv(ms) {
  return (ms / 1000).toFixed(3) + ' km/s'
}

function fmtTime(seconds) {
  if (seconds < 3600) return (seconds / 60).toFixed(1) + ' min'
  if (seconds < 86400) return (seconds / 3600).toFixed(2) + ' h'
  return (seconds / 86400).toFixed(2) + ' days'
}

function fmtPeriod(seconds) {
  return (seconds / 60).toFixed(1) + ' min'
}

export default function KestrelMissionPage() {
  const [activeSubTab, setActiveSubTab] = useState('launch')

  const [launchSiteId, setLaunchSiteId] = useState('ksc')
  const [altitudeKm, setAltitudeKm] = useState(550)
  const [incDeg, setIncDeg] = useState(97.6)
  const [raanDeg, setRaanDeg] = useState(0)
  const [ecc, setEcc] = useState(0)
  const [missionType, setMissionType] = useState('observation')

  const [kestrelCZML, setKestrelCZML] = useState(null)
  const [kestrelElements, setKestrelElements] = useState(null)
  const [computingOrbit, setComputingOrbit] = useState(false)

  const [targetQuery, setTargetQuery] = useState('')
  const [targetResults, setTargetResults] = useState([])
  const [targetSearching, setTargetSearching] = useState(false)
  const [selectedTarget, setSelectedTarget] = useState(null)
  const [targetElements, setTargetElements] = useState(null)
  const [targetFetchError, setTargetFetchError] = useState(null)

  const [maneuverResult, setManeuverResult] = useState(null)
  const [maneuverCZML, setManeuverCZML] = useState(null)
  const [computingManeuver, setComputingManeuver] = useState(false)
  const [maneuverError, setManeuverError] = useState(null)

  const searchDebounce = useRef(null)

  const launchSite = LAUNCH_SITES.find((s) => s.id === launchSiteId) || LAUNCH_SITES[0]

  const applyPreset = (preset) => {
    setAltitudeKm(preset.altitudeKm)
    setIncDeg(preset.incDeg)
    setEcc(0)
  }

  const handleComputeOrbit = useCallback(() => {
    setComputingOrbit(true)
    setTimeout(() => {
      try {
        const sma = altitudeToSMA(altitudeKm)
        const inc = incDeg * DEG
        const raan = raanDeg * DEG
        const period = orbitalPeriod(sma)
        const duration = period * 3

        const elements = { sma, ecc, inc, raan, argPerigee: 0, meanAnomaly0: 0 }
        setKestrelElements(elements)

        const stepSec = Math.max(10, Math.round(period / 200))
        const points = propagateOrbit(elements, duration, stepSec)

        const startIso = new Date().toISOString()
        const czml = generateCZML(
          [
            {
              id: 'kestrel',
              label: 'KESTREL',
              points,
              color: [52, 152, 219, 255],
              trailTime: period,
              leadTime: 0,
              pointSize: 12,
              pathWidth: 2.5,
            },
          ],
          startIso,
          duration
        )
        setKestrelCZML(czml)
      } finally {
        setComputingOrbit(false)
      }
    }, 20)
  }, [altitudeKm, incDeg, raanDeg, ecc])

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
    setSelectedTarget({ name, noradId, objectType: canonical.object_type || '' })
    setTargetQuery(name)
    setTargetResults([])
    setTargetElements(null)
    setTargetFetchError(null)
    setManeuverResult(null)
    setManeuverCZML(null)

    if (!noradId) {
      setTargetFetchError('No NORAD ID for this object — cannot fetch TLE.')
      return
    }

    try {
      const res = await apiFetch(`${API_ENDPOINTS.TLE}?norad_id=${noradId}`)
      if (!res.ok) throw new Error(`TLE fetch failed: HTTP ${res.status}`)
      const data = await res.json()
      const tleLines = Array.isArray(data) ? data : (data.data || [])
      const entry = tleLines[0]
      if (!entry) throw new Error('No TLE found for this object.')
      const line1 = entry.tle_line1 || entry.line1
      const line2 = entry.tle_line2 || entry.line2
      if (!line1 || !line2) throw new Error('TLE lines missing in response.')
      const els = parseTLE(line1, line2)
      if (!els) throw new Error('Failed to parse TLE data.')
      setTargetElements(els)
    } catch (err) {
      setTargetFetchError(err.message)
    }
  }

  const handlePlanManeuver = useCallback(() => {
    if (!kestrelElements) {
      setManeuverError('Plan a Kestrel orbit first in the Launch Planner.')
      return
    }
    if (!targetElements) {
      setManeuverError('Select a target and wait for TLE to load.')
      return
    }

    setComputingManeuver(true)
    setManeuverError(null)

    setTimeout(() => {
      try {
        const r1 = kestrelElements.sma
        const r2 = targetElements.sma
        const transfer = hohmannTransfer(r1, r2)
        const burnWindow = computeOptimalBurnWindow(r1, r2)

        const incKestrel = kestrelElements.inc
        const incTarget = targetElements.inc
        const incChangeDeg = Math.abs(incKestrel - incTarget) * RAD

        setManeuverResult({
          ...transfer,
          ...burnWindow,
          kestrelAlt: smaToAltitude(r1).toFixed(1),
          targetAlt: smaToAltitude(r2).toFixed(1),
          incChangeDeg: incChangeDeg.toFixed(2),
          kestrelPeriod: orbitalPeriod(r1),
          targetPeriod: orbitalPeriod(r2),
        })

        const startIso = new Date().toISOString()
        const kestrelPeriod = orbitalPeriod(r1)
        const targetPeriod = orbitalPeriod(r2)
        const totalDuration = transfer.transferTime * 2 + Math.max(kestrelPeriod, targetPeriod) * 2

        const kestrelPoints = propagateOrbit(
          kestrelElements,
          kestrelPeriod * 2,
          Math.max(10, Math.round(kestrelPeriod / 200))
        )

        const targetPoints = propagateOrbit(
          targetElements,
          targetPeriod * 2,
          Math.max(10, Math.round(targetPeriod / 200))
        )

        const transferPoints = propagateTransferOrbit(
          r1, r2,
          kestrelElements.raan,
          kestrelElements.inc,
          kestrelPeriod * 2,
          120
        )

        const czml = generateCZML(
          [
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
              label: selectedTarget?.name || 'TARGET',
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
              points: transferPoints,
              color: [241, 196, 15, 255],
              trailTime: transfer.transferTime,
              leadTime: 0,
              pointSize: 6,
              pathWidth: 3,
            },
          ],
          startIso,
          totalDuration
        )
        setManeuverCZML(czml)
      } catch (err) {
        setManeuverError(err.message)
      } finally {
        setComputingManeuver(false)
      }
    }, 20)
  }, [kestrelElements, targetElements, selectedTarget])

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
        >
          Maneuver Planner
        </button>
      </div>

      <div className="km-body">
        {activeSubTab === 'launch' && (
          <>
            <aside className="km-sidebar">
              <section className="km-section">
                <h3>Mission Configuration</h3>
                <div className="km-field">
                  <label>Mission Type</label>
                  <div className="km-mission-types">
                    {[
                      { id: 'observation', label: 'Observation', icon: '👁' },
                      { id: 'inspection', label: 'Inspection', icon: '🔍' },
                      { id: 'servicing', label: 'Servicing', icon: '🔧' },
                    ].map((m) => (
                      <button
                        key={m.id}
                        className={`km-mission-btn${missionType === m.id ? ' active' : ''}`}
                        onClick={() => setMissionType(m.id)}
                      >
                        <span>{m.icon}</span>
                        <span>{m.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </section>

              <section className="km-section">
                <h3>Launch Site</h3>
                <div className="km-field">
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
                </div>
                <div className="km-site-info">
                  <span className="km-site-coord">
                    {launchSite.lat.toFixed(2)}° N / {launchSite.lon.toFixed(2)}° E
                  </span>
                  <span className="km-site-note">
                    Min reachable inclination: {Math.abs(launchSite.lat).toFixed(1)}°
                  </span>
                </div>
              </section>

              <section className="km-section">
                <h3>Orbit Parameters</h3>

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
                    <span>0° (equatorial)</span>
                    <span>90° (polar)</span>
                  </div>
                </div>

                <div className="km-field">
                  <label>
                    RAAN
                    <span className="km-field-value">{raanDeg.toFixed(0)}°</span>
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={359}
                    step={1}
                    value={raanDeg}
                    onChange={(e) => setRaanDeg(Number(e.target.value))}
                    className="km-slider"
                  />
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
                    <strong>{fmtPeriod(orbitalPeriod(altitudeToSMA(altitudeKm)))}</strong>
                  </div>
                  <div className="km-sum-item">
                    <span>SMA</span>
                    <strong>{(altitudeToSMA(altitudeKm) / 1000).toFixed(0)} km</strong>
                  </div>
                </div>

                <button
                  className="km-primary-btn"
                  onClick={handleComputeOrbit}
                  disabled={computingOrbit}
                >
                  {computingOrbit ? 'Computing…' : '↗ Compute Orbit'}
                </button>
              </section>
            </aside>

            <KestrelCesiumViewer
              czmlData={kestrelCZML}
              launchSite={launchSite}
              emptyMessage="Configure orbit parameters and click Compute Orbit to visualize the planned Kestrel trajectory."
            />
          </>
        )}

        {activeSubTab === 'maneuver' && (
          <>
            <aside className="km-sidebar">
              <section className="km-section">
                <h3>Kestrel Parking Orbit</h3>
                {kestrelElements ? (
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
                      <span>Eccentricity</span>
                      <strong>{kestrelElements.ecc.toFixed(4)}</strong>
                    </div>
                  </div>
                ) : (
                  <p className="km-hint-text">
                    No orbit configured. Set parameters in the{' '}
                    <button className="km-link-btn" onClick={() => setActiveSubTab('launch')}>
                      Launch Planner
                    </button>{' '}
                    first.
                  </p>
                )}
              </section>

              <section className="km-section">
                <h3>Target Selection</h3>
                <div className="km-field">
                  <label>Search catalog</label>
                  <div className="km-search-wrapper">
                    <input
                      type="text"
                      className="km-input"
                      placeholder="Name, NORAD ID, or debris…"
                      value={targetQuery}
                      onChange={handleTargetSearch}
                    />
                    {targetSearching && <span className="km-spinner" />}
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

                {selectedTarget && (
                  <div className="km-selected-target">
                    <div className="km-target-name">{selectedTarget.name}</div>
                    {selectedTarget.noradId && (
                      <div className="km-target-meta">
                        <span className="km-badge">NORAD {selectedTarget.noradId}</span>
                        {selectedTarget.objectType && (
                          <span className="km-badge km-badge-type">{selectedTarget.objectType}</span>
                        )}
                      </div>
                    )}
                    {targetFetchError && (
                      <p className="km-error">{targetFetchError}</p>
                    )}
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
                  </div>
                )}
              </section>

              {maneuverError && (
                <p className="km-error">{maneuverError}</p>
              )}

              <button
                className="km-primary-btn"
                onClick={handlePlanManeuver}
                disabled={computingManeuver || !kestrelElements || !targetElements}
              >
                {computingManeuver ? 'Computing…' : '⚡ Plan Maneuver'}
              </button>

              {maneuverResult && (
                <section className="km-section km-results">
                  <h3>Maneuver Results</h3>

                  <div className="km-result-block">
                    <div className="km-result-title">Hohmann Transfer</div>
                    <div className="km-result-rows">
                      <div className="km-result-row">
                        <span>ΔV₁ (departure burn)</span>
                        <strong className="km-dv">{fmtDv(maneuverResult.dv1)}</strong>
                      </div>
                      <div className="km-result-row">
                        <span>ΔV₂ (arrival burn)</span>
                        <strong className="km-dv">{fmtDv(maneuverResult.dv2)}</strong>
                      </div>
                      <div className="km-result-row km-total">
                        <span>Total ΔV</span>
                        <strong className="km-dv">{fmtDv(maneuverResult.dvTotal)}</strong>
                      </div>
                      <div className="km-result-row">
                        <span>Transfer time</span>
                        <strong>{fmtTime(maneuverResult.transferTime)}</strong>
                      </div>
                      <div className="km-result-row">
                        <span>Synodic period</span>
                        <strong>{fmtTime(maneuverResult.synodicPeriod)}</strong>
                      </div>
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
                    </div>
                    {parseFloat(maneuverResult.incChangeDeg) > 5 && (
                      <p className="km-warn-note">
                        Plane change required (+{(parseFloat(maneuverResult.incChangeDeg) * 0.05).toFixed(3)} km/s approx). Budget additional ΔV.
                      </p>
                    )}
                  </div>
                </section>
              )}
            </aside>

            <KestrelCesiumViewer
              czmlData={maneuverCZML}
              launchSite={null}
              emptyMessage="Select a target and plan a maneuver to visualize the Hohmann transfer trajectory."
            />
          </>
        )}
      </div>
    </div>
  )
}

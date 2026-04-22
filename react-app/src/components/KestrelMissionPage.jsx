import { useState, useRef, useCallback, useEffect } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import KestrelCesiumViewer from './KestrelCesiumViewer'
import KestrelDataDials from './KestrelDataDials'
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
  computeJ2RAANScenario,
  deorbitBurn,
  generateCZML,
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

function fmtRendezvous(seconds) {
  if (!isFinite(seconds)) return '∞'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days}d ${hours}h ${mins}m`
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins} min`
}

function fmtArrivalDate(seconds) {
  if (!isFinite(seconds)) return '—'
  const d = new Date(Date.now() + seconds * 1000)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`
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

const MATERIALS = ['solar_panel', 'aluminum_alloy', 'titanium', 'carbon_fiber', 'multilayer_insulation']

function seededRng(seed) {
  let s = seed
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff
    return (s >>> 0) / 4294967296
  }
}

function nameToSeed(str) {
  let h = 5381
  for (let i = 0; i < str.length; i++) h = (h * 33 ^ str.charCodeAt(i)) | 0
  return Math.abs(h)
}

function generateSimulatedObservations(targetName, noradId, altKm) {
  const rng = seededRng(nameToSeed((targetName || '') + (noradId || '') + (altKm || 500)))
  const COUNT = 10
  const baseHealth = 40 + rng() * 40
  const baseMass = 200 + rng() * 1800
  const material = MATERIALS[Math.floor(rng() * MATERIALS.length)]
  const baseReflect = 0.15 + rng() * 0.6
  const baseSpin = rng() * 3
  const basePerigeeDrift = -(rng() * 0.01)
  const basePerigee = altKm || 500
  const now = Date.now()

  return Array.from({ length: COUNT }, (_, i) => {
    const progress = i / (COUNT - 1)
    const r = seededRng(nameToSeed(targetName + i))
    const jitter = () => r() * 2 - 1

    const range = 60 * Math.pow(1 - progress * 0.95, 1.5) + r() * 2
    const health = baseHealth + progress * 15 + jitter() * 5
    const stability = progress > 0.4 ? r() > 0.8 : r() > 0.3

    return {
      object_name: targetName,
      norad_id: noradId,
      observation_epoch: new Date(now + i * 8000).toISOString(),
      source: 'KESTREL-1',
      derived_health_score: Math.min(100, Math.max(0, health)),
      estimated_mass_kg: baseMass + jitter() * 20,
      spin_rate_rpm: Math.max(0, baseSpin - progress * baseSpin * 0.7 + jitter() * 0.2),
      attitude: {
        roll_deg: jitter() * 30 * (1 - progress * 0.6),
        pitch_deg: jitter() * 15 * (1 - progress * 0.5),
        yaw_deg: jitter() * 45 * (1 - progress * 0.6),
        stability_flag: stability,
      },
      thermal: {
        surface_temp_K: 270 + jitter() * 30 + progress * 10,
        temp_variance_30d: Math.max(0, 15 - progress * 12 + r() * 5),
        anomaly_flag: health < 45 && r() > 0.6,
      },
      material_signature: {
        reflectivity_index: baseReflect + jitter() * 0.05 * (1 - progress * 0.8),
        inferred_material: material,
        confidence: 0.3 + progress * 0.65 + r() * 0.05,
      },
      proximity_state: {
        range_km: Math.max(0.1, range),
        relative_velocity_ms: Math.max(0.01, 0.5 - progress * 0.45 + r() * 0.05),
      },
      maneuver_indicator: {
        delta_v_residual_ms: Math.max(0, 2 - progress * 1.8 + r() * 0.3),
        confidence: 0.4 + progress * 0.5,
        flag: progress < 0.2 && r() > 0.5,
      },
      orbital_decay_indicator: {
        perigee_drift_km_per_day: basePerigeeDrift + jitter() * 0.002,
        estimated_perigee_km: basePerigee + jitter() * 2,
      },
    }
  })
}

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

  const [altitudeKm, setAltitudeKm] = useState(550)
  const [incDeg, setIncDeg] = useState(97.6)
  const [ecc] = useState(0)

  const [kestrelCZML, setKestrelCZML] = useState(null)
  const [kestrelElements, setKestrelElements] = useState(null)
  const [computing, setComputing] = useState(false)
  const [computeError, setComputeError] = useState(null)

  const [maneuverResult, setManeuverResult] = useState(null)
  const [maneuverCZML, setManeuverCZML] = useState(null)
  const [scenarios, setScenarios] = useState(null)
  const [activeScenario, setActiveScenario] = useState(null)
  const [executedScenario, setExecutedScenario] = useState(null)

  const [advisorLoading, setAdvisorLoading] = useState(false)
  const [advisorResult, setAdvisorResult] = useState(null)
  const [advisorError, setAdvisorError] = useState(null)
  const [advisorClarifyQuestion, setAdvisorClarifyQuestion] = useState(null)
  const [advisorClarification, setAdvisorClarification] = useState('')
  const [advisorConstraints, setAdvisorConstraints] = useState('')

  const [gmatPlan, setGmatPlan] = useState(null)
  const [gmatPlanLoading, setGmatPlanLoading] = useState(false)
  const [gmatPlanError, setGmatPlanError] = useState(null)
  const [gmatPlanHistory, setGmatPlanHistory] = useState([])
  const [gmatHistoryLoading, setGmatHistoryLoading] = useState(false)
  const [gmatPlanCZML, setGmatPlanCZML] = useState(null)
  const [kestrelProxyNoradId, setKestrelProxyNoradId] = useState('')
  const [gmatMaxDv, setGmatMaxDv] = useState(0.5)
  const [gmatMaxDays, setGmatMaxDays] = useState(14)

  const [liveObs, setLiveObs] = useState([])
  const [collectRunning, setCollectRunning] = useState(false)
  const [collectDone, setCollectDone] = useState(false)
  const allSimObs = useRef([])
  const collectIntervalRef = useRef(null)

  const searchDebounce = useRef(null)
  const kestrelPointsRef = useRef(null)
  const targetPointsRef = useRef(null)

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
      setAltitudeKm(Math.max(250, Math.round(smaToAltitude(els.sma)) - 100))
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
    setAdvisorResult(null)
    setAdvisorClarifyQuestion(null)
    setAdvisorError(null)

    setTimeout(() => {
      try {
        const elements = {
          sma: altitudeToSMA(altitudeKm),
          ecc,
          inc: targetElements ? targetElements.inc : incDeg * (Math.PI / 180),
          raan: targetElements ? targetElements.raan : 0,
          argPerigee: 0,
          meanAnomaly0: 0,
        }
        setKestrelElements(elements)

        const period = orbitalPeriod(elements.sma)
        const kestrelStep = Math.max(10, Math.round(period / 240))

        const startIso = new Date().toISOString()

        const launchPoints = propagateOrbit(elements, period * 3, kestrelStep)
        const launchCzml = generateCZML(
          [
            {
              id: 'kestrel',
              label: 'KESTREL',
              points: launchPoints,
              color: [52, 152, 219, 255],
              trailTime: period / 3,
              leadTime: period * 0.67,
              pointSize: 12,
              pathWidth: 2.5,
            },
          ],
          startIso,
          period * 3
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

          // Preview arc: show full phase-alignment wait before burn (capped at 60 parking orbits for display)
          const arcPreviewWait = Math.min(burnWindow.synodicPeriod / 2, period * 60)
          const TWO_PI_local = 2 * Math.PI
          const n_park = Math.sqrt(3.986004418e14 / Math.pow(r1, 3))
          const M_burn_preview = ((elements.meanAnomaly0 + n_park * arcPreviewWait) % TWO_PI_local + TWO_PI_local) % TWO_PI_local
          const previewArc = propagateTransferOrbit(r1, r2, elements.raan, elements.inc, arcPreviewWait, 150, M_burn_preview)

          // Propagate orbits to cover the preview mission window
          const previewDuration = arcPreviewWait + transfer.transferTime + targetPeriod * 2
          const kestrelPoints = propagateOrbit(elements, previewDuration, kestrelStep)
          const targetPoints = propagateOrbit(targetElements, previewDuration, targetStep)

          kestrelPointsRef.current = { points: kestrelPoints, period, elements }
          targetPointsRef.current = { points: targetPoints, period: targetPeriod }

          const computed = computeManeuverScenarios(r1, r2)
          const j2Scenario = computeJ2RAANScenario(elements, targetElements)
          setScenarios(j2Scenario ? [...computed, j2Scenario] : computed)
          setActiveScenario(null)
          setExecutedScenario(null)

          setManeuverCZML(buildManeuverCZML(startIso, kestrelPoints, period, targetPoints, targetPeriod, previewArc, transfer.transferTime, selectedTarget.name, elements, targetElements))
          setActiveSubTab('maneuver')
        }
      } catch (err) {
        setComputeError(err.message)
      } finally {
        setComputing(false)
      }
    }, 20)
  }, [altitudeKm, incDeg, ecc, targetElements, selectedTarget, missionType])

  function buildManeuverCZML(startIso, kestrelPoints, kestrelPeriod, targetPoints, targetPeriod, arcPoints, arcDuration, targetName, kestrelEls, targetEls) {
    const arcStartSec = arcPoints.length > 0 ? arcPoints[0].t : 0
    const arcEndSec = arcPoints.length > 0 ? arcPoints[arcPoints.length - 1].t : arcDuration
    const TWO_PI_BM = 2 * Math.PI

    let unifiedKestrelPoints = kestrelPoints
    if (kestrelEls && targetEls && arcPoints.length > 1) {
      const phase1 = kestrelPoints.filter(p => p.t < arcStartSec)
      const phase2 = arcPoints

      const arrivalPt = arcPoints[arcPoints.length - 1]
      const arrivalTime = arrivalPt.t

      const totalDuration = Math.max(
        kestrelPoints[kestrelPoints.length - 1]?.t || 0,
        targetPoints[targetPoints.length - 1]?.t || 0
      )
      const phase3Duration = Math.max(0, totalDuration - arrivalTime)

      if (phase3Duration > 60) {
        const { inc: incT, raan: raanT, sma: smaT } = targetEls
        const cosO = Math.cos(raanT), sinO = Math.sin(raanT)
        const cosI = Math.cos(incT), sinI = Math.sin(incT)
        const xOrb = cosO * arrivalPt.x + sinO * arrivalPt.y
        const yOrb = -sinO * cosI * arrivalPt.x + cosO * cosI * arrivalPt.y + sinI * arrivalPt.z
        const arrivalArgLat = ((Math.atan2(yOrb, xOrb) % TWO_PI_BM) + TWO_PI_BM) % TWO_PI_BM

        const circEls = {
          sma: smaT,
          ecc: 0,
          inc: incT,
          raan: raanT,
          argPerigee: 0,
          meanAnomaly0: arrivalArgLat,
        }
        const step3 = Math.max(30, Math.round(orbitalPeriod(smaT) / 120))
        const phase3Raw = propagateOrbit(circEls, phase3Duration, step3)
        const phase3 = phase3Raw.map(p => ({ t: p.t + arrivalTime, x: p.x, y: p.y, z: p.z }))
        unifiedKestrelPoints = [...phase1, ...phase2, ...phase3]
      } else {
        unifiedKestrelPoints = [...phase1, ...phase2]
      }
    }

    const sats = [
      {
        id: 'kestrel',
        label: 'KESTREL',
        points: unifiedKestrelPoints,
        color: [52, 152, 219, 255],
        trailTime: kestrelPeriod * 2,
        leadTime: 0,
        pointSize: 12,
        pathWidth: 2.5,
        labelOffsetY: -28,
      },
      {
        id: 'target',
        label: targetName || 'TARGET',
        points: targetPoints,
        color: [231, 76, 60, 255],
        trailTime: targetPeriod / 3,
        leadTime: targetPeriod * 0.67,
        pointSize: 10,
        pathWidth: 2,
        labelOffsetY: 18,
      },
      {
        id: 'transfer',
        label: 'Transfer Arc',
        points: arcPoints,
        color: [241, 196, 15, 180],
        trailTime: arcDuration,
        leadTime: 0,
        pointSize: 3,
        pathWidth: 2,
        availStartSec: arcStartSec,
        availEndSec: arcEndSec,
        noLabel: true,
      },
    ]
    const totalDuration = Math.max(
      unifiedKestrelPoints[unifiedKestrelPoints.length - 1]?.t || 0,
      targetPoints[targetPoints.length - 1]?.t || 0,
      arcEndSec
    )
    return generateCZML(sats, startIso, totalDuration)
  }

  const handleExecuteScenario = useCallback((scenario) => {
    setExecutedScenario(scenario)
    const kp = kestrelPointsRef.current
    const tp = targetPointsRef.current
    if (!kp || !tp || !kestrelElements || !targetElements) return

    // Cap displayed wait time at 80 parking orbits so the animation stays manageable
    const displayWaitTime = Math.min(scenario.waitTime || 0, kp.period * 80)
    const displayScenario = { ...scenario, waitTime: displayWaitTime }

    // Re-propagate both orbits to cover the full display mission duration
    const displayDuration = displayWaitTime + scenario.transferTime + tp.period * 3
    const kStep = Math.max(30, Math.round(kp.period / 120))
    const tStep = Math.max(30, Math.round(tp.period / 120))
    const newKestrelPoints = propagateOrbit(kestrelElements, displayDuration, kStep)
    const newTargetPoints = propagateOrbit(targetElements, displayDuration, tStep)

    const arcPoints = propagateScenarioArc(displayScenario, kestrelElements, targetElements.sma, 150)
    const startIso = new Date().toISOString()
    const czml = buildManeuverCZML(
      startIso,
      newKestrelPoints,
      kp.period,
      newTargetPoints,
      tp.period,
      arcPoints,
      scenario.transferTime,
      selectedTarget?.name,
      kestrelElements,
      targetElements
    )
    setManeuverCZML(czml)
  }, [kestrelElements, targetElements, selectedTarget])

  const handleGetAIRecommendation = useCallback(async (clarification = '') => {
    if (!scenarios || !kestrelElements || !targetElements || !selectedTarget) return
    setAdvisorLoading(true)
    setAdvisorError(null)
    setAdvisorResult(null)
    if (!clarification) {
      setAdvisorClarifyQuestion(null)
      setAdvisorClarification('')
    }

    const RAD_LOCAL = 180 / Math.PI
    const missionContext = {
      target: {
        name: selectedTarget.name,
        alt_km: smaToAltitude(targetElements.sma).toFixed(1),
        inc_deg: (targetElements.inc * RAD_LOCAL).toFixed(2),
        raan_deg: (targetElements.raan * RAD_LOCAL).toFixed(2),
      },
      kestrel: {
        alt_km: smaToAltitude(kestrelElements.sma).toFixed(1),
        inc_deg: (kestrelElements.inc * RAD_LOCAL).toFixed(2),
        raan_deg: (kestrelElements.raan * RAD_LOCAL).toFixed(2),
      },
      mission_type: missionType,
      scenarios: scenarios.map((sc) => ({
        id: sc.id,
        name: sc.name,
        tag: sc.tag,
        dvTotal: sc.dvTotal,
        dv1: sc.dv1,
        dv2: sc.dv2,
        transferTime: sc.transferTime,
        waitTime: sc.waitTime,
        driftAltKm: sc.driftAltKm,
        dRaanDeg: sc.dRaanDeg,
      })),
      constraints: advisorConstraints,
    }

    try {
      const res = await apiFetch(API_ENDPOINTS.AGENT.KESTREL_MISSION, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mission_context: missionContext, clarification: clarification || '' }),
      })
      let data
      try {
        data = await res.json()
      } catch {
        throw new Error(`Server error (HTTP ${res.status}) — check backend logs`)
      }
      if (!res.ok) throw new Error(data.detail || 'Advisor request failed')
      if (data.clarifying_question) {
        setAdvisorClarifyQuestion(data.clarifying_question)
        setAdvisorClarification('')
      } else if (data.error) {
        setAdvisorError(data.error)
      } else {
        setAdvisorResult(data)
        setAdvisorClarifyQuestion(null)
      }
    } catch (err) {
      setAdvisorError(err.message)
    } finally {
      setAdvisorLoading(false)
    }
  }, [scenarios, kestrelElements, targetElements, selectedTarget, missionType, advisorConstraints])

  const handleStartCollection = useCallback(() => {
    if (!selectedTarget || !targetElements) return
    if (collectIntervalRef.current) clearInterval(collectIntervalRef.current)
    const altKm = Math.round(smaToAltitude(targetElements.sma))
    allSimObs.current = generateSimulatedObservations(
      selectedTarget.name,
      selectedTarget.noradId,
      altKm
    )
    setLiveObs([allSimObs.current[0]])
    setCollectRunning(true)
    setCollectDone(false)
    let idx = 1
    collectIntervalRef.current = setInterval(() => {
      if (idx >= allSimObs.current.length) {
        clearInterval(collectIntervalRef.current)
        collectIntervalRef.current = null
        setCollectRunning(false)
        setCollectDone(true)
        return
      }
      setLiveObs(prev => [...prev, allSimObs.current[idx]])
      idx++
    }, 2500)
  }, [selectedTarget, targetElements])

  useEffect(() => {
    return () => {
      if (collectIntervalRef.current) clearInterval(collectIntervalRef.current)
    }
  }, [])

  const handleComputeGmatPlan = useCallback(async () => {
    if (!selectedTarget?.noradId) {
      setGmatPlanError('Select a target object with a NORAD ID first.')
      return
    }
    if (!kestrelProxyNoradId || isNaN(parseInt(kestrelProxyNoradId))) {
      setGmatPlanError('Enter a valid NORAD ID for the Kestrel proxy spacecraft.')
      return
    }
    setGmatPlanLoading(true)
    setGmatPlanError(null)
    setGmatPlan(null)
    try {
      const res = await apiFetch(API_ENDPOINTS.KESTREL.MANEUVER_PLAN, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kestrel_norad_id: parseInt(kestrelProxyNoradId),
          target_norad_id: selectedTarget.noradId,
          mission_type: missionType,
          max_dv_km_s: gmatMaxDv,
          max_time_days: gmatMaxDays,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Plan computation failed')
      setGmatPlan(data)
      fetchGmatPlanHistory()
    } catch (err) {
      setGmatPlanError(err.message)
    } finally {
      setGmatPlanLoading(false)
    }
  }, [selectedTarget, kestrelProxyNoradId, missionType, gmatMaxDv, gmatMaxDays])

  const fetchGmatPlanHistory = useCallback(async () => {
    setGmatHistoryLoading(true)
    try {
      const params = new URLSearchParams({ limit: 10 })
      if (selectedTarget?.noradId) params.set('target_norad_id', selectedTarget.noradId)
      const res = await apiFetch(`${API_ENDPOINTS.KESTREL.MANEUVER_PLANS}?${params}`)
      const data = await res.json()
      setGmatPlanHistory(data.data || [])
    } catch {
    } finally {
      setGmatHistoryLoading(false)
    }
  }, [selectedTarget])

  useEffect(() => {
    if (activeSubTab === 'gmatplan') fetchGmatPlanHistory()
  }, [activeSubTab, fetchGmatPlanHistory])

  useEffect(() => {
    if (!gmatPlan?.kestrel_kep || !gmatPlan?.target_kep) {
      setGmatPlanCZML(null)
      return
    }
    try {
      const D2R = Math.PI / 180
      const kKep = gmatPlan.kestrel_kep
      const tKep = gmatPlan.target_kep

      const kEls = {
        sma: kKep.sma_km * 1000,
        ecc: kKep.ecc,
        inc: kKep.inc_deg * D2R,
        raan: kKep.raan_deg * D2R,
        argPerigee: kKep.aop_deg * D2R,
        meanAnomaly0: kKep.ta_deg * D2R,
      }
      const tEls = {
        sma: tKep.sma_km * 1000,
        ecc: tKep.ecc,
        inc: tKep.inc_deg * D2R,
        raan: tKep.raan_deg * D2R,
        argPerigee: tKep.aop_deg * D2R,
        meanAnomaly0: tKep.ta_deg * D2R,
      }

      const waitSecs = gmatPlan.wait_time_s || 0
      const transferSecs = gmatPlan.transfer_time_s || 3600
      const tPeriod = orbitalPeriod(tEls.sma)
      const kPeriod = orbitalPeriod(kEls.sma)
      const displayDuration = waitSecs + transferSecs + tPeriod * 2
      const kStep = Math.max(30, Math.round(kPeriod / 120))
      const tStep = Math.max(30, Math.round(tPeriod / 120))

      const kPoints = propagateOrbit(kEls, displayDuration, kStep)
      const tPoints = propagateOrbit(tEls, displayDuration, tStep)
      const arcPoints = propagateTransferOrbit(kEls.sma, tEls.sma, kEls.raan, kEls.inc, waitSecs, 150)

      const startIso = gmatPlan.burn1_epoch || new Date().toISOString()
      const arcStart = arcPoints.length > 0 ? arcPoints[0].t : waitSecs
      const arcEnd = arcPoints.length > 0 ? arcPoints[arcPoints.length - 1].t : waitSecs + transferSecs

      const czml = generateCZML(
        [
          {
            id: 'kestrel',
            label: `KESTREL (NORAD ${gmatPlan.kestrel_norad_id})`,
            points: kPoints,
            color: [52, 152, 219, 255],
            trailTime: kPeriod * 2,
            leadTime: 0,
            pointSize: 12,
            pathWidth: 2.5,
            labelOffsetY: -28,
          },
          {
            id: 'target',
            label: selectedTarget?.name || `Target (NORAD ${gmatPlan.target_norad_id})`,
            points: tPoints,
            color: [231, 76, 60, 255],
            trailTime: tPeriod / 3,
            leadTime: tPeriod * 0.67,
            pointSize: 10,
            pathWidth: 2,
            labelOffsetY: 18,
          },
          {
            id: 'transfer',
            label: 'Transfer Arc',
            points: arcPoints,
            color: [241, 196, 15, 180],
            trailTime: transferSecs,
            leadTime: 0,
            pointSize: 3,
            pathWidth: 2,
            availStartSec: arcStart,
            availEndSec: arcEnd,
            noLabel: true,
          },
        ],
        startIso,
        displayDuration
      )
      setGmatPlanCZML(czml)
    } catch {
      setGmatPlanCZML(null)
    }
  }, [gmatPlan, selectedTarget])

  const kestrelPeriod = orbitalPeriod(altitudeToSMA(altitudeKm))

  return (
    <div className="km-page">
      <div className="km-subnav">
        <button
          className={activeSubTab === 'launch' ? 'active' : ''}
          onClick={() => setActiveSubTab('launch')}
        >
          Intercept Setup
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
        <button
          className={activeSubTab === 'advisor' ? 'active' : ''}
          onClick={() => setActiveSubTab('advisor')}
          disabled={!scenarios}
          title={!scenarios ? 'Plan a mission first' : ''}
        >
          AI Mission Advisor
          {advisorResult && <span className="km-tab-badge">✓</span>}
        </button>
        <button
          className={activeSubTab === 'gmatplan' ? 'active' : ''}
          onClick={() => setActiveSubTab('gmatplan')}
          disabled={!selectedTarget}
          title={!selectedTarget ? 'Select a target object first' : ''}
        >
          GMAT Maneuver Plan
          {gmatPlan && <span className="km-tab-badge">✓</span>}
        </button>
        <button
          className={`km-collect-tab${activeSubTab === 'collection' ? ' active' : ''}`}
          onClick={() => setActiveSubTab('collection')}
          disabled={!executedScenario}
          title={!executedScenario ? 'Execute a maneuver scenario first' : ''}
        >
          📡 Data Collection
          {collectDone && <span className="km-tab-badge">✓</span>}
          {collectRunning && <span className="km-tab-pulse" />}
        </button>
      </div>

      <div className="km-body">
        {activeSubTab === 'launch' && (
          <>
            <aside className="km-sidebar">

              <div className="km-kestrel-status-banner">
                <span className="km-kestrel-orbit-dot" />
                <span>KESTREL-1 · IN ORBIT · {altitudeKm.toLocaleString()} km</span>
              </div>

              <section className="km-section">
                <h3>1 — Intercept Target</h3>
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
                        ↑ Kestrel will maneuver from {altitudeKm} km → {Math.round(smaToAltitude(targetElements.sma))} km
                        {targetTleSource === 'db_cached' && (
                          <span className="km-badge km-badge-cached" title="Live TLE unavailable — using last known TLE from database"> cached TLE</span>
                        )}
                      </p>
                    )}
                  </div>
                )}
              </section>

              <section className="km-section">
                <h3>2 — Collection Mode</h3>
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
                <h3>3 — Kestrel Current Orbit</h3>
                <div className="km-field">
                  <label>
                    Altitude
                    <span className="km-field-value">{altitudeKm.toLocaleString()} km</span>
                  </label>
                  <input
                    type="range"
                    min={200}
                    max={2000}
                    step={10}
                    value={altitudeKm}
                    onChange={(e) => setAltitudeKm(Number(e.target.value))}
                    className="km-slider"
                  />
                  <div className="km-slider-labels">
                    <span>200 km</span>
                    <span>2 000 km</span>
                  </div>
                </div>
                <div className="km-orbit-summary">
                  <div className="km-sum-item">
                    <span>Period</span>
                    <strong>{fmtPeriod(kestrelPeriod)}</strong>
                  </div>
                  <div className="km-sum-item">
                    <span>Inclination</span>
                    <strong>{targetElements ? (targetElements.inc * RAD).toFixed(1) : incDeg.toFixed(1)}°</strong>
                  </div>
                </div>
                <p className="km-hint-text">
                  Inclination and orbital plane are matched to the target when selected.
                </p>

                {computeError && <p className="km-error">{computeError}</p>}

                <button
                  className="km-primary-btn"
                  onClick={handlePlanMission}
                  disabled={computing || !selectedTarget}
                >
                  {computing ? 'Computing…' : '🛰 Plan Intercept'}
                </button>
                {!selectedTarget && (
                  <p className="km-hint-text" style={{ textAlign: 'center', marginTop: '4px' }}>
                    Select a target object above first
                  </p>
                )}
              </section>
            </aside>

            <KestrelCesiumViewer
              czmlData={maneuverCZML || kestrelCZML}
              launchSite={null}
              emptyMessage="Select a target object and click Plan Intercept to compute the maneuver trajectory."
            />
          </>
        )}

        {activeSubTab === 'maneuver' && (
          <>
            <aside className="km-sidebar">
              <section className="km-section">
                <h3>Intercept Summary</h3>
                <div className="km-mission-summary-row">
                  <span className="km-sum-label">Target</span>
                  <span className="km-sum-value-inline">{selectedTarget?.name || '—'}</span>
                </div>
                <div className="km-mission-summary-row">
                  <span className="km-sum-label">Mode</span>
                  <span className="km-sum-value-inline">
                    {MISSION_TYPES.find((m) => m.id === missionType)?.icon}{' '}
                    {MISSION_TYPES.find((m) => m.id === missionType)?.label}
                  </span>
                </div>
              </section>

              {kestrelElements && (
                <section className="km-section">
                  <h3>Kestrel Starting Orbit</h3>
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
                            {sc.driftAltKm !== undefined && (
                              <div className="km-sc-stat">
                                <span>Drift Orbit</span>
                                <strong>{sc.driftAltKm} km</strong>
                              </div>
                            )}
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

                    <div className="km-result-block km-timeline-block">
                      <div className="km-result-title">Mission Timeline to Rendezvous</div>
                      <div className="km-result-rows">
                        <div className="km-result-row km-timeline-phase">
                          <span>Phase 1 — Phase alignment</span>
                          <strong>{fmtRendezvous(maneuverResult.synodicPeriod / 2)}</strong>
                        </div>
                        <div className="km-result-row km-timeline-note">
                          <span className="km-timeline-sub">Kestrel phasing in lower orbit until optimal burn geometry</span>
                        </div>
                        <div className="km-result-row km-timeline-phase">
                          <span>Phase 2 — Hohmann transfer</span>
                          <strong>{fmtRendezvous(maneuverResult.transferTime)}</strong>
                        </div>
                        <div className="km-result-row km-timeline-note">
                          <span className="km-timeline-sub">ΔV₁ burn → coast → ΔV₂ circularization</span>
                        </div>
                        <div className="km-result-row km-total">
                          <span>Total time to rendezvous</span>
                          <strong className="km-timeline-total">{fmtRendezvous(maneuverResult.synodicPeriod / 2 + maneuverResult.transferTime)}</strong>
                        </div>
                        <div className="km-result-row km-timeline-arrival-row">
                          <span>Est. arrival</span>
                          <strong className="km-timeline-arrival">{fmtArrivalDate(maneuverResult.synodicPeriod / 2 + maneuverResult.transferTime)}</strong>
                        </div>
                      </div>
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

              {executedScenario && (
                <section className="km-section">
                  <button
                    className="km-collect-cta-btn"
                    onClick={() => {
                      setActiveSubTab('collection')
                      if (!collectRunning && !collectDone) handleStartCollection()
                    }}
                  >
                    📡 Begin Data Collection →
                  </button>
                  <p className="km-hint-text" style={{ textAlign: 'center', marginTop: '2px' }}>
                    Kestrel is in proximity — start collecting sensor data
                  </p>
                </section>
              )}
            </aside>

            <KestrelCesiumViewer
              czmlData={maneuverCZML}
              launchSite={null}
              targetLabel={selectedTarget?.name}
              clockMultiplier={2000}
              emptyMessage="Complete the Launch Planner to see the full mission trajectory — Kestrel orbit (blue), target (red), transfer arc (yellow)."
            />
          </>
        )}

        {activeSubTab === 'advisor' && (
          <>
            <aside className="km-sidebar">
              <section className="km-section">
                <h3>Mission Context</h3>
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
                {kestrelElements && targetElements && (
                  <div className="km-orbit-summary" style={{ marginTop: '0.5rem' }}>
                    <div className="km-sum-item">
                      <span>Kestrel Alt</span>
                      <strong>{smaToAltitude(kestrelElements.sma).toFixed(0)} km</strong>
                    </div>
                    <div className="km-sum-item">
                      <span>Target Alt</span>
                      <strong>{smaToAltitude(targetElements.sma).toFixed(0)} km</strong>
                    </div>
                    <div className="km-sum-item">
                      <span>RAAN Δ</span>
                      <strong>{Math.abs(((targetElements.raan - kestrelElements.raan) * RAD + 540) % 360 - 180).toFixed(1)}°</strong>
                    </div>
                  </div>
                )}
              </section>

              <section className="km-section">
                <h3>AI Mission Advisor</h3>
                <p className="km-hint-text" style={{ marginBottom: '0.5rem' }}>
                  Optionally describe constraints, then ask the AI to recommend the best maneuver scenario.
                </p>
                <div className="km-field">
                  <label>Operator Constraints</label>
                  <input
                    type="text"
                    className="km-input"
                    placeholder="e.g. ΔV budget &lt;200 m/s, rendezvous within 2 weeks…"
                    value={advisorConstraints}
                    onChange={(e) => setAdvisorConstraints(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !advisorLoading && handleGetAIRecommendation()}
                  />
                </div>
                <button
                  className="km-advisor-btn"
                  onClick={() => handleGetAIRecommendation()}
                  disabled={advisorLoading}
                >
                  {advisorLoading ? 'Analyzing…' : 'Get AI Recommendation'}
                </button>

                {advisorError && <p className="km-error">{advisorError}</p>}

                {advisorClarifyQuestion && (
                  <div className="km-advisor-clarify">
                    <div className="km-advisor-clarify-label">Clarification needed</div>
                    <p className="km-advisor-clarify-q">{advisorClarifyQuestion}</p>
                    <div className="km-advisor-clarify-row">
                      <input
                        type="text"
                        className="km-input"
                        placeholder="Your answer…"
                        value={advisorClarification}
                        onChange={(e) => setAdvisorClarification(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && advisorClarification.trim()) {
                            handleGetAIRecommendation(advisorClarification)
                          }
                        }}
                      />
                      <button
                        className="km-advisor-btn"
                        style={{ width: 'auto', marginTop: 0 }}
                        onClick={() => handleGetAIRecommendation(advisorClarification)}
                        disabled={advisorLoading || !advisorClarification.trim()}
                      >
                        Submit
                      </button>
                    </div>
                  </div>
                )}

                {advisorResult && scenarios && (() => {
                  const recSc = scenarios.find((sc) => sc.id === advisorResult.recommended_scenario_id)
                  const confidenceColor = { high: '#3fb950', medium: '#e6b454', low: '#f85149' }[advisorResult.confidence] || '#888'
                  return (
                    <div className="km-advisor-result">
                      <div className="km-advisor-result-header">
                        <span className="km-advisor-rec-label">Recommended</span>
                        {recSc && (
                          <span className="km-advisor-rec-name" style={{ color: recSc.tagColor }}>
                            {recSc.name}
                          </span>
                        )}
                        <span className="km-advisor-confidence" style={{ color: confidenceColor }}>
                          {advisorResult.confidence} confidence
                        </span>
                      </div>
                      <p className="km-advisor-reasoning">{advisorResult.reasoning}</p>
                      {advisorResult.trade_off_summary && (
                        <p className="km-advisor-tradeoff">
                          <strong>Trade-off:</strong> {advisorResult.trade_off_summary}
                        </p>
                      )}
                      {advisorResult.caveats && (
                        <p className="km-advisor-caveat">{advisorResult.caveats}</p>
                      )}
                      {recSc && (
                        <button
                          className="km-btn-execute"
                          style={{ width: '100%', marginTop: '0.75rem' }}
                          onClick={() => {
                            handleExecuteScenario(recSc)
                            setActiveSubTab('maneuver')
                          }}
                        >
                          Execute & View on Globe
                        </button>
                      )}
                    </div>
                  )
                })()}
              </section>

              {scenarios && (
                <section className="km-section">
                  <h3>Available Scenarios</h3>
                  {scenarios.map((sc) => (
                    <div key={sc.id} className="km-advisor-scenario-row"
                      style={{ borderLeft: `3px solid ${sc.tagColor}` }}>
                      <div className="km-advisor-sc-name">{sc.name}</div>
                      <div className="km-advisor-sc-stats">
                        <span>ΔV {(sc.dvTotal / 1000).toFixed(3)} km/s</span>
                        <span>{sc.waitTime === 0 ? 'No wait' : fmtTime(sc.waitTime) + ' wait'}</span>
                      </div>
                    </div>
                  ))}
                </section>
              )}
            </aside>

            <KestrelCesiumViewer
              czmlData={maneuverCZML || kestrelCZML}
              launchSite={null}
              targetLabel={selectedTarget?.name}
              emptyMessage="The AI advisor will recommend and execute the best scenario — the result appears here."
            />
          </>
        )}

        {activeSubTab === 'gmatplan' && (
          <>
            <aside className="km-sidebar">
              <section className="km-section">
                <h3>GMAT Maneuver Compute</h3>
                <div className="km-mission-summary-row">
                  <span className="km-sum-label">Target</span>
                  <span className="km-sum-value-inline">{selectedTarget?.name || '—'}</span>
                </div>
                <div className="km-mission-summary-row">
                  <span className="km-sum-label">NORAD</span>
                  <span className="km-sum-value-inline">{selectedTarget?.noradId || '—'}</span>
                </div>
                <div className="km-field" style={{ marginTop: '0.75rem' }}>
                  <label>Kestrel Proxy NORAD ID</label>
                  <input
                    type="number"
                    className="km-input"
                    placeholder="e.g. 25544 (ISS as proxy)"
                    value={kestrelProxyNoradId}
                    onChange={(e) => setKestrelProxyNoradId(e.target.value)}
                  />
                  <p className="km-hint-text">A real catalogued object whose TLE defines Kestrel&apos;s starting orbit.</p>
                </div>
                <div className="km-field">
                  <label>
                    Max ΔV budget
                    <span className="km-field-value">{gmatMaxDv.toFixed(2)} km/s</span>
                  </label>
                  <input
                    type="range"
                    min={0.05}
                    max={2.0}
                    step={0.05}
                    value={gmatMaxDv}
                    onChange={(e) => setGmatMaxDv(parseFloat(e.target.value))}
                    className="km-slider"
                  />
                </div>
                <div className="km-field">
                  <label>
                    Max time
                    <span className="km-field-value">{gmatMaxDays} days</span>
                  </label>
                  <input
                    type="range"
                    min={1}
                    max={60}
                    step={1}
                    value={gmatMaxDays}
                    onChange={(e) => setGmatMaxDays(parseInt(e.target.value))}
                    className="km-slider"
                  />
                </div>
                {gmatPlanError && <p className="km-error">{gmatPlanError}</p>}
                <button
                  className="km-primary-btn"
                  onClick={handleComputeGmatPlan}
                  disabled={gmatPlanLoading || !selectedTarget?.noradId}
                >
                  {gmatPlanLoading ? 'Computing…' : '⚙ Compute GMAT Plan'}
                </button>
              </section>

              {gmatPlan && (
                <section className="km-section km-results">
                  <h3>
                    Plan Result
                    <span
                      className="km-badge"
                      style={{
                        marginLeft: '0.5rem',
                        fontSize: '0.68rem',
                        background: gmatPlan.gmat_verified ? '#1a4a1a' : '#2a2a1a',
                        color: gmatPlan.gmat_verified ? '#3fb950' : '#e6b454',
                        border: `1px solid ${gmatPlan.gmat_verified ? '#3fb950' : '#e6b454'}`,
                        padding: '1px 6px',
                        borderRadius: '4px',
                        verticalAlign: 'middle',
                      }}
                    >
                      {gmatPlan.gmat_verified ? 'GMAT Verified' : 'Analytical'}
                    </span>
                  </h3>
                  <div className="km-result-block">
                    <div className="km-result-title">ΔV Budget</div>
                    <div className="km-result-rows">
                      <div className="km-result-row">
                        <span>ΔV₁ departure</span>
                        <strong className="km-dv">{gmatPlan.dv1_ms?.toFixed(1)} m/s</strong>
                      </div>
                      <div className="km-result-row">
                        <span>ΔV₂ arrival</span>
                        <strong className="km-dv">{gmatPlan.dv2_ms?.toFixed(1)} m/s</strong>
                      </div>
                      {gmatPlan.dv_plane_change_ms > 0.1 && (
                        <div className="km-result-row">
                          <span>Plane change</span>
                          <strong className="km-warn">{gmatPlan.dv_plane_change_ms?.toFixed(1)} m/s</strong>
                        </div>
                      )}
                      <div className="km-result-row km-total">
                        <span>Total ΔV</span>
                        <strong className="km-dv">{gmatPlan.dv_total_ms?.toFixed(1)} m/s</strong>
                      </div>
                    </div>
                  </div>
                  <div className="km-result-block">
                    <div className="km-result-title">Timeline</div>
                    <div className="km-result-rows">
                      <div className="km-result-row">
                        <span>Phase wait</span>
                        <strong>{fmtTime(gmatPlan.wait_time_s)}</strong>
                      </div>
                      <div className="km-result-row">
                        <span>Transfer arc</span>
                        <strong>{fmtTime(gmatPlan.transfer_time_s)}</strong>
                      </div>
                      <div className="km-result-row km-total">
                        <span>Total time</span>
                        <strong>{fmtTime(gmatPlan.total_time_s)}</strong>
                      </div>
                    </div>
                  </div>
                  <div className="km-result-block">
                    <div className="km-result-title">Burn Epochs</div>
                    <div className="km-result-rows">
                      <div className="km-result-row">
                        <span>Burn 1</span>
                        <strong style={{ fontSize: '0.72rem' }}>
                          {gmatPlan.burn1_epoch ? new Date(gmatPlan.burn1_epoch).toUTCString().slice(0, 22) : '—'}
                        </strong>
                      </div>
                      <div className="km-result-row">
                        <span>Burn 2</span>
                        <strong style={{ fontSize: '0.72rem' }}>
                          {gmatPlan.burn2_epoch ? new Date(gmatPlan.burn2_epoch).toUTCString().slice(0, 22) : '—'}
                        </strong>
                      </div>
                    </div>
                  </div>
                  {gmatPlan.closest_approach_km != null && (
                    <div className="km-result-block">
                      <div className="km-result-title">Closest Approach</div>
                      <div className="km-result-rows">
                        <div className="km-result-row">
                          <span>Range</span>
                          <strong style={{ color: '#3fb950' }}>{gmatPlan.closest_approach_km?.toFixed(2)} km</strong>
                        </div>
                        <div className="km-result-row">
                          <span>Time</span>
                          <strong style={{ fontSize: '0.72rem' }}>
                            {gmatPlan.closest_approach_time ? new Date(gmatPlan.closest_approach_time).toUTCString().slice(0, 22) : '—'}
                          </strong>
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="km-result-block">
                    <div className="km-result-title">Orbital Delta</div>
                    <div className="km-result-rows">
                      <div className="km-result-row">
                        <span>Kestrel alt</span>
                        <strong>{gmatPlan.kestrel_alt_km?.toFixed(0)} km</strong>
                      </div>
                      <div className="km-result-row">
                        <span>Target alt</span>
                        <strong>{gmatPlan.target_alt_km?.toFixed(0)} km</strong>
                      </div>
                      <div className="km-result-row">
                        <span>Inc Δ</span>
                        <strong className={gmatPlan.inc_diff_deg > 5 ? 'km-warn' : ''}>
                          {gmatPlan.inc_diff_deg?.toFixed(2)}°
                        </strong>
                      </div>
                      <div className="km-result-row">
                        <span>RAAN Δ</span>
                        <strong>{gmatPlan.raan_diff_deg?.toFixed(2)}°</strong>
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {gmatPlanHistory.length > 0 && (
                <section className="km-section">
                  <h3>Plan History</h3>
                  <p className="km-hint-text" style={{ marginBottom: '0.5rem' }}>
                    {gmatHistoryLoading ? 'Loading…' : `${gmatPlanHistory.length} saved plan(s) for this target`}
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    {gmatPlanHistory.map((p, i) => (
                      <div
                        key={p._key || i}
                        className="km-scenario-card"
                        style={{ cursor: 'pointer', padding: '0.5rem 0.75rem' }}
                        onClick={() => setGmatPlan(p)}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.75rem', color: '#888' }}>
                            {new Date(p.created_at).toLocaleDateString()}
                          </span>
                          <span
                            style={{
                              fontSize: '0.68rem',
                              padding: '1px 5px',
                              borderRadius: '3px',
                              background: p.gmat_verified ? '#1a4a1a' : '#2a2a1a',
                              color: p.gmat_verified ? '#3fb950' : '#e6b454',
                            }}
                          >
                            {p.gmat_verified ? 'GMAT' : 'Analytical'}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.8rem', marginTop: '0.2rem' }}>
                          ΔV {p.dv_total_ms?.toFixed(0)} m/s · {fmtTime(p.total_time_s)}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </aside>

            <div className="km-gmat-plan-main">
              {gmatPlan ? (
                <div className="km-gmat-upper">
                <div className="km-gmat-metrics">
                  <div className="km-gmat-metrics-title">
                    {gmatPlan.gmat_verified ? '⚙ GMAT High-Fidelity' : '⚡ Analytical'} Maneuver Plan
                    {' · '}{selectedTarget?.name}
                  </div>
                  <div className="km-gmat-metric-grid">
                    <div className="km-gmat-metric-card">
                      <div className="km-gmat-metric-label">ΔV₁ Departure</div>
                      <div className="km-gmat-metric-value" style={{ color: '#3498db' }}>
                        {gmatPlan.dv1_ms?.toFixed(1)}
                      </div>
                      <div className="km-gmat-metric-unit">m/s</div>
                    </div>
                    <div className="km-gmat-metric-card">
                      <div className="km-gmat-metric-label">ΔV₂ Arrival</div>
                      <div className="km-gmat-metric-value" style={{ color: '#3498db' }}>
                        {gmatPlan.dv2_ms?.toFixed(1)}
                      </div>
                      <div className="km-gmat-metric-unit">m/s</div>
                    </div>
                    <div className="km-gmat-metric-card km-gmat-metric-card--highlight">
                      <div className="km-gmat-metric-label">Total ΔV</div>
                      <div className="km-gmat-metric-value" style={{ color: '#e74c3c' }}>
                        {gmatPlan.dv_total_ms?.toFixed(1)}
                      </div>
                      <div className="km-gmat-metric-unit">m/s</div>
                    </div>
                    <div className="km-gmat-metric-card">
                      <div className="km-gmat-metric-label">Phase Wait</div>
                      <div className="km-gmat-metric-value" style={{ color: '#f39c12' }}>
                        {(gmatPlan.wait_time_s / 3600).toFixed(1)}
                      </div>
                      <div className="km-gmat-metric-unit">hours</div>
                    </div>
                    <div className="km-gmat-metric-card">
                      <div className="km-gmat-metric-label">Transfer Time</div>
                      <div className="km-gmat-metric-value" style={{ color: '#f39c12' }}>
                        {(gmatPlan.transfer_time_s / 3600).toFixed(1)}
                      </div>
                      <div className="km-gmat-metric-unit">hours</div>
                    </div>
                    <div className="km-gmat-metric-card km-gmat-metric-card--highlight">
                      <div className="km-gmat-metric-label">Total Time</div>
                      <div className="km-gmat-metric-value" style={{ color: '#e67e22' }}>
                        {(gmatPlan.total_time_s / 86400).toFixed(2)}
                      </div>
                      <div className="km-gmat-metric-unit">days</div>
                    </div>
                    <div className="km-gmat-metric-card">
                      <div className="km-gmat-metric-label">Kestrel Alt</div>
                      <div className="km-gmat-metric-value" style={{ color: '#2ecc71' }}>
                        {gmatPlan.kestrel_alt_km?.toFixed(0)}
                      </div>
                      <div className="km-gmat-metric-unit">km</div>
                    </div>
                    <div className="km-gmat-metric-card">
                      <div className="km-gmat-metric-label">Target Alt</div>
                      <div className="km-gmat-metric-value" style={{ color: '#2ecc71' }}>
                        {gmatPlan.target_alt_km?.toFixed(0)}
                      </div>
                      <div className="km-gmat-metric-unit">km</div>
                    </div>
                    <div className="km-gmat-metric-card">
                      <div className="km-gmat-metric-label">Inc Δ</div>
                      <div
                        className="km-gmat-metric-value"
                        style={{ color: gmatPlan.inc_diff_deg > 5 ? '#e74c3c' : '#2ecc71' }}
                      >
                        {gmatPlan.inc_diff_deg?.toFixed(2)}
                      </div>
                      <div className="km-gmat-metric-unit">deg</div>
                    </div>
                    {gmatPlan.closest_approach_km != null && (
                      <div className="km-gmat-metric-card km-gmat-metric-card--highlight">
                        <div className="km-gmat-metric-label">Closest Approach</div>
                        <div className="km-gmat-metric-value" style={{ color: '#3fb950' }}>
                          {gmatPlan.closest_approach_km?.toFixed(2)}
                        </div>
                        <div className="km-gmat-metric-unit">km</div>
                      </div>
                    )}
                    {gmatPlan.dv_plane_change_ms > 0.1 && (
                      <div className="km-gmat-metric-card">
                        <div className="km-gmat-metric-label">Plane Change Cost</div>
                        <div className="km-gmat-metric-value" style={{ color: '#e74c3c' }}>
                          {gmatPlan.dv_plane_change_ms?.toFixed(1)}
                        </div>
                        <div className="km-gmat-metric-unit">m/s</div>
                      </div>
                    )}
                  </div>
                  <div className="km-gmat-burn-epochs">
                    <div className="km-gmat-epoch-row">
                      <span className="km-gmat-epoch-label">🔥 Burn 1</span>
                      <span className="km-gmat-epoch-val">
                        {gmatPlan.burn1_epoch ? new Date(gmatPlan.burn1_epoch).toUTCString() : '—'}
                      </span>
                    </div>
                    <div className="km-gmat-epoch-row">
                      <span className="km-gmat-epoch-label">🔥 Burn 2</span>
                      <span className="km-gmat-epoch-val">
                        {gmatPlan.burn2_epoch ? new Date(gmatPlan.burn2_epoch).toUTCString() : '—'}
                      </span>
                    </div>
                    {gmatPlan.closest_approach_time && (
                      <div className="km-gmat-epoch-row">
                        <span className="km-gmat-epoch-label">🎯 Closest Approach</span>
                        <span className="km-gmat-epoch-val">
                          {new Date(gmatPlan.closest_approach_time).toUTCString()}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
                </div>
              ) : (
                <div className="km-collect-empty">
                  <div style={{ fontSize: '3rem', marginBottom: '0.75rem' }}>⚙</div>
                  <p>
                    Enter a <strong>Kestrel proxy NORAD ID</strong> and click{' '}
                    <strong>Compute GMAT Plan</strong> to calculate the high-fidelity
                    maneuver parameters for this rendezvous.
                  </p>
                  <p className="km-hint-text" style={{ marginTop: '0.5rem' }}>
                    Without GMAT installed, results use the analytical Hohmann transfer model.
                    With GMAT, the plan is verified using an RK89/EGM96 hi-fi propagator.
                  </p>
                </div>
              )}
              <div className="km-gmat-cesium">
                <KestrelCesiumViewer
                  czmlData={gmatPlanCZML}
                  launchSite={null}
                  targetLabel={selectedTarget?.name}
                  clockMultiplier={2000}
                  emptyMessage="Compute a GMAT maneuver plan to see the intercept trajectory — Kestrel (blue), target (red), transfer arc (yellow)."
                />
              </div>
            </div>
          </>
        )}

        {activeSubTab === 'collection' && (
          <>
            <aside className="km-sidebar">
              <section className="km-section">
                <h3>Collection Status</h3>
                <div className="km-collect-target-card">
                  <div className="km-collect-target-label">Target</div>
                  <div className="km-collect-target-name">{selectedTarget?.name || '—'}</div>
                  {selectedTarget?.noradId && (
                    <span className="km-badge">NORAD {selectedTarget.noradId}</span>
                  )}
                </div>
                <div className="km-collect-status-row">
                  <div className={`km-collect-indicator${collectRunning ? ' km-collect-indicator-live' : collectDone ? ' km-collect-indicator-done' : ''}`} />
                  <span className="km-collect-status-text">
                    {collectRunning ? 'COLLECTING LIVE DATA…' : collectDone ? 'COLLECTION COMPLETE' : 'STANDBY'}
                  </span>
                </div>
                <div className="km-collect-progress-wrap">
                  <div className="km-collect-progress-bar">
                    <div
                      className="km-collect-progress-fill"
                      style={{ width: `${liveObs.length * 10}%` }}
                    />
                  </div>
                  <span className="km-collect-progress-label">{liveObs.length} / 10 obs</span>
                </div>
                {liveObs.length > 0 && (
                  <div className="km-orbit-summary" style={{ marginTop: '0.5rem' }}>
                    <div className="km-sum-item">
                      <span>Range</span>
                      <strong style={{ color: '#2980b9' }}>
                        {liveObs[liveObs.length - 1].proximity_state?.range_km?.toFixed(1)} km
                      </strong>
                    </div>
                    <div className="km-sum-item">
                      <span>Health</span>
                      <strong style={{ color: liveObs[liveObs.length - 1].derived_health_score >= 70 ? '#27ae60' : liveObs[liveObs.length - 1].derived_health_score >= 40 ? '#f39c12' : '#e74c3c' }}>
                        {liveObs[liveObs.length - 1].derived_health_score?.toFixed(1)}
                      </strong>
                    </div>
                    <div className="km-sum-item">
                      <span>Rel. Vel.</span>
                      <strong>{liveObs[liveObs.length - 1].proximity_state?.relative_velocity_ms?.toFixed(2)} m/s</strong>
                    </div>
                    <div className="km-sum-item">
                      <span>Material</span>
                      <strong style={{ fontSize: '0.72rem' }}>
                        {liveObs[liveObs.length - 1].material_signature?.inferred_material?.replace(/_/g, ' ')}
                      </strong>
                    </div>
                  </div>
                )}
              </section>

              <section className="km-section">
                {!collectRunning && !collectDone && (
                  <button className="km-collect-cta-btn" onClick={handleStartCollection}>
                    📡 Start Collection
                  </button>
                )}
                {collectDone && (
                  <button className="km-primary-btn" onClick={handleStartCollection}>
                    ↺ Restart Collection
                  </button>
                )}
                {collectRunning && (
                  <div className="km-collect-scanning">
                    <div className="km-collect-scan-ring" />
                    <span>Scanning…</span>
                  </div>
                )}
              </section>

              {executedScenario && (
                <section className="km-section">
                  <h3>Executed Maneuver</h3>
                  <div className="km-mission-summary-row">
                    <span className="km-sum-label">Scenario</span>
                    <span className="km-sum-value-inline">{executedScenario.name}</span>
                  </div>
                  <div className="km-mission-summary-row">
                    <span className="km-sum-label">ΔV Total</span>
                    <span className="km-sum-value-inline km-dv">{fmtDv(executedScenario.dvTotal)}</span>
                  </div>
                  <div className="km-mission-summary-row">
                    <span className="km-sum-label">Transfer</span>
                    <span className="km-sum-value-inline">{fmtTime(executedScenario.transferTime)}</span>
                  </div>
                </section>
              )}
            </aside>

            <div className="km-collection-main">
              {liveObs.length > 0 ? (
                <KestrelDataDials
                  observations={liveObs}
                  satelliteName={selectedTarget?.name}
                />
              ) : (
                <div className="km-collect-empty">
                  <div style={{ fontSize: '3rem', marginBottom: '0.75rem' }}>📡</div>
                  <p>Click <strong>Start Collection</strong> to begin streaming sensor data from Kestrel.</p>
                </div>
              )}
              <KestrelCesiumViewer
                czmlData={maneuverCZML}
                launchSite={null}
                targetLabel={selectedTarget?.name}
                emptyMessage="Trajectory view — Kestrel (blue) in proximity to target (red)."
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}

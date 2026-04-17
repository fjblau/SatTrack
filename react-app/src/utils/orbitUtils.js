const GM = 3.986004418e14
const RE = 6.3781e6
const TWO_PI = 2 * Math.PI

function solveKepler(M, e, maxIter = 100, tol = 1e-12) {
  let E = e < 0.8 ? M : Math.PI
  for (let i = 0; i < maxIter; i++) {
    const dE = (M - E + e * Math.sin(E)) / (1 - e * Math.cos(E))
    E += dE
    if (Math.abs(dE) < tol) break
  }
  return E
}

function keplerToECI(a, e, i, raan, argPerigee, trueAnomaly) {
  const p = a * (1 - e * e)
  const r = p / (1 + e * Math.cos(trueAnomaly))

  const xp = r * Math.cos(trueAnomaly)
  const yp = r * Math.sin(trueAnomaly)

  const cosO = Math.cos(raan), sinO = Math.sin(raan)
  const cosI = Math.cos(i), sinI = Math.sin(i)
  const cosW = Math.cos(argPerigee), sinW = Math.sin(argPerigee)

  const x =
    (cosO * cosW - sinO * sinW * cosI) * xp +
    (-cosO * sinW - sinO * cosW * cosI) * yp
  const y =
    (sinO * cosW + cosO * sinW * cosI) * xp +
    (-sinO * sinW + cosO * cosW * cosI) * yp
  const z = sinW * sinI * xp + cosW * sinI * yp

  return [x, y, z]
}

export function propagateOrbit(elements, durationSeconds, stepSeconds) {
  const { sma, ecc, inc, raan, argPerigee, meanAnomaly0 } = elements
  const n = Math.sqrt(GM / Math.pow(sma, 3))
  const points = []
  for (let t = 0; t <= durationSeconds; t += stepSeconds) {
    const M = ((meanAnomaly0 + n * t) % TWO_PI + TWO_PI) % TWO_PI
    const E = solveKepler(M, ecc)
    const sqrtTerm = Math.sqrt(1 - ecc * ecc)
    const nu = Math.atan2(sqrtTerm * Math.sin(E), Math.cos(E) - ecc)
    const [x, y, z] = keplerToECI(sma, ecc, inc, raan, argPerigee, nu)
    points.push({ t, x, y, z })
  }
  return points
}

export function altitudeToSMA(altitudeKm) {
  return (altitudeKm * 1000) + RE
}

export function smaToAltitude(sma) {
  return (sma - RE) / 1000
}

export function orbitalPeriod(sma) {
  return TWO_PI * Math.sqrt(Math.pow(sma, 3) / GM)
}

export function parseTLE(line1, line2) {
  try {
    const inc = parseFloat(line2.substring(8, 16)) * (Math.PI / 180)
    const raan = parseFloat(line2.substring(17, 25)) * (Math.PI / 180)
    const eccStr = '0.' + line2.substring(26, 33).trim()
    const ecc = parseFloat(eccStr)
    const argPerigee = parseFloat(line2.substring(34, 42)) * (Math.PI / 180)
    const meanAnomaly0 = parseFloat(line2.substring(43, 51)) * (Math.PI / 180)
    const meanMotionRevDay = parseFloat(line2.substring(52, 63))
    const n = (meanMotionRevDay * TWO_PI) / 86400
    const sma = Math.pow(GM / (n * n), 1 / 3)
    return { sma, ecc, inc, raan, argPerigee, meanAnomaly0 }
  } catch {
    return null
  }
}

export function hohmannTransfer(r1, r2) {
  const v1 = Math.sqrt(GM / r1)
  const v2 = Math.sqrt(GM / r2)
  const at = (r1 + r2) / 2
  const vt1 = Math.sqrt(GM * (2 / r1 - 1 / at))
  const vt2 = Math.sqrt(GM * (2 / r2 - 1 / at))
  const dv1 = Math.abs(vt1 - v1)
  const dv2 = Math.abs(v2 - vt2)
  const transferTime = Math.PI * Math.sqrt(Math.pow(at, 3) / GM)
  return { dv1, dv2, dvTotal: dv1 + dv2, transferTime, at }
}

export function computeOptimalBurnWindow(r1, r2) {
  const n2 = Math.sqrt(GM / Math.pow(r2, 3))
  const at = (r1 + r2) / 2
  const transferTime = Math.PI * Math.sqrt(Math.pow(at, 3) / GM)
  const requiredPhaseAngle = Math.PI - n2 * transferTime
  const n1 = Math.sqrt(GM / Math.pow(r1, 3))
  const synodicRate = Math.abs(n1 - n2)
  const synodicPeriod = synodicRate > 0 ? TWO_PI / synodicRate : Infinity
  return { requiredPhaseAngle, synodicPeriod, transferTime }
}

export function launchSiteToOrbitElements(siteLat, siteLon, altKm, incDeg, eccParam = 0) {
  const lat = siteLat * (Math.PI / 180)
  const lon = siteLon * (Math.PI / 180)
  const inc = incDeg * (Math.PI / 180)
  const sma = altitudeToSMA(altKm)

  let M0, raan

  const ratio = Math.sin(lat) / Math.sin(inc)

  if (Math.abs(ratio) <= 1) {
    M0 = Math.asin(ratio)
    const A = Math.cos(M0)
    const B = Math.sin(M0) * Math.cos(inc)
    raan = Math.atan2(A * Math.sin(lon) - B * Math.cos(lon), A * Math.cos(lon) + B * Math.sin(lon))
  } else {
    M0 = (lat >= 0 ? 1 : -1) * Math.PI / 2
    raan = lon
  }

  return { sma, ecc: eccParam, inc, raan, argPerigee: 0, meanAnomaly0: M0 }
}

export function deorbitBurn(rTarget, rDeorbitPerigeeKm = 200) {
  const rDeorbit = RE + rDeorbitPerigeeKm * 1000
  const vCircular = Math.sqrt(GM / rTarget)
  const aTransfer = (rTarget + rDeorbit) / 2
  const vTransferAtApogee = Math.sqrt(GM * (2 / rTarget - 1 / aTransfer))
  const dvDeorbit = Math.abs(vCircular - vTransferAtApogee)
  const deorbitTime = Math.PI * Math.sqrt(Math.pow(aTransfer, 3) / GM)
  return { dvDeorbit, deorbitTime, rDeorbit, altKm: rDeorbitPerigeeKm }
}

export function propagateTransferOrbit(r1, r2, raan, incKestrel, startSeconds, steps = 100) {
  const at = (r1 + r2) / 2
  const ecc = Math.abs(r2 - r1) / (r1 + r2)
  const argPerigee = r1 < r2 ? 0 : Math.PI
  const transferTime = Math.PI * Math.sqrt(Math.pow(at, 3) / GM)
  const n = Math.sqrt(GM / Math.pow(at, 3))
  const M0 = 0
  const stepDuration = transferTime / steps

  const points = []
  for (let i = 0; i <= steps; i++) {
    const t = i * stepDuration
    const M = ((M0 + n * t) % TWO_PI + TWO_PI) % TWO_PI
    const E = solveKepler(M, ecc)
    const sqrtTerm = Math.sqrt(1 - ecc * ecc)
    const nu = Math.atan2(sqrtTerm * Math.sin(E), Math.cos(E) - ecc)
    const [x, y, z] = keplerToECI(at, ecc, incKestrel, raan, argPerigee, nu)
    points.push({ t: startSeconds + t, x, y, z })
  }
  return points
}

export function generateCZML(satellites, startIso, totalDurationSeconds) {
  const startMs = new Date(startIso).getTime()
  const endMs = startMs + totalDurationSeconds * 1000
  const endIso = new Date(endMs).toISOString()

  const doc = {
    id: 'document',
    name: 'Kestrel Mission',
    version: '1.0',
    clock: {
      interval: `${startIso}/${endIso}`,
      currentTime: startIso,
      multiplier: 60,
      range: 'LOOP_STOP',
      step: 'SYSTEM_CLOCK_MULTIPLIER',
    },
  }

  const entities = satellites.map((sat) => {
    const cartesian = []
    for (const pt of sat.points) {
      cartesian.push(pt.t, pt.x, pt.y, pt.z)
    }

    const availStart = startIso
    const availEnd = sat.availEnd || endIso

    return {
      id: sat.id,
      name: sat.label,
      availability: `${availStart}/${availEnd}`,
      position: {
        interpolationAlgorithm: 'LAGRANGE',
        interpolationDegree: 5,
        referenceFrame: 'INERTIAL',
        epoch: startIso,
        cartesian,
      },
      point: {
        pixelSize: sat.pointSize || 10,
        color: { rgba: sat.color },
        outlineColor: { rgba: [255, 255, 255, 120] },
        outlineWidth: 1,
      },
      path: {
        resolution: 60,
        leadTime: sat.leadTime !== undefined ? sat.leadTime : 0,
        trailTime: sat.trailTime || 7200,
        material: {
          solidColor: { color: { rgba: [...sat.color.slice(0, 3), 160] } },
        },
        width: sat.pathWidth || 2,
      },
      label: {
        text: sat.label,
        font: '13pt sans-serif',
        fillColor: { rgba: [255, 255, 255, 220] },
        outlineColor: { rgba: [0, 0, 0, 160] },
        outlineWidth: 2,
        style: 'FILL_AND_OUTLINE',
        verticalOrigin: 'BOTTOM',
        pixelOffset: { cartesian2: [0, -14] },
        show: true,
      },
    }
  })

  return [doc, ...entities]
}

export function computeManeuverScenarios(r1, r2) {
  const base = hohmannTransfer(r1, r2)
  const burnWindow = computeOptimalBurnWindow(r1, r2)
  const targetPeriod = orbitalPeriod(r2)

  const s1 = {
    id: 'hohmann',
    name: 'Hohmann Transfer',
    tag: 'OPTIMAL',
    tagColor: '#3fb950',
    desc: 'Two-burn minimum-energy transfer. Wait for phase alignment, then execute.',
    dv1: base.dv1,
    dv2: base.dv2,
    dvTotal: base.dvTotal,
    transferTime: base.transferTime,
    waitTime: burnWindow.synodicPeriod / 2,
    at: base.at,
    arcMode: 'hohmann',
  }

  const fastDv1 = base.dv1 * 1.42
  const fastDv2 = base.dv2 * 1.42
  const fastAt = r1 < r2
    ? (r1 + r2 * 1.55) / 2
    : (r1 * 1.55 + r2) / 2
  const fastTime = Math.PI * Math.sqrt(Math.pow(fastAt, 3) / GM) * 0.62
  const s2 = {
    id: 'fast',
    name: 'Fast Intercept',
    tag: 'FAST',
    tagColor: '#e6b454',
    desc: 'Depart immediately with higher thrust. No phase wait — ~42% more ΔV, ~38% less transit time.',
    dv1: fastDv1,
    dv2: fastDv2,
    dvTotal: fastDv1 + fastDv2,
    transferTime: fastTime,
    waitTime: 0,
    at: fastAt,
    arcMode: 'fast',
  }

  const phaseDv = base.dvTotal * 0.72
  const phaseTime = base.transferTime + targetPeriod * 1.8
  const s3 = {
    id: 'phased',
    name: 'Phased Rendezvous',
    tag: 'EFFICIENT',
    tagColor: '#58a6ff',
    desc: 'Phasing orbit approach: drift into alignment over multiple passes. ~28% less ΔV, longer time.',
    dv1: phaseDv * 0.55,
    dv2: phaseDv * 0.45,
    dvTotal: phaseDv,
    transferTime: phaseTime,
    waitTime: burnWindow.synodicPeriod * 0.25,
    at: (r1 + r2) / 2,
    arcMode: 'phased',
    phaseOrbitSMA: r1 < r2 ? r1 * 0.985 : r1 * 1.015,
  }

  return [s1, s2, s3]
}

export function propagateScenarioArc(scenario, kestrelElements, r2, steps = 150) {
  const { r1, raan, inc } = { r1: kestrelElements.sma, raan: kestrelElements.raan, inc: kestrelElements.inc }
  const startOffset = 0

  if (scenario.arcMode === 'hohmann') {
    return propagateTransferOrbit(r1, r2, raan, inc, startOffset, steps)
  }

  if (scenario.arcMode === 'fast') {
    const at = scenario.at
    const ecc = Math.abs(at * 2 - r1 - r2) / (r1 + (r1 < r2 ? r2 : r1))
    const argP = r1 < r2 ? 0 : Math.PI
    const n = Math.sqrt(GM / Math.pow(at, 3))
    const transferTime = scenario.transferTime
    const stepDur = transferTime / steps
    const points = []
    for (let i = 0; i <= steps; i++) {
      const t = i * stepDur
      const M = ((n * t) % TWO_PI + TWO_PI) % TWO_PI
      const E = solveKepler(M, ecc)
      const nu = Math.atan2(Math.sqrt(1 - ecc * ecc) * Math.sin(E), Math.cos(E) - ecc)
      const [x, y, z] = keplerToECI(at, ecc, inc, raan, argP, nu)
      points.push({ t: startOffset + t, x, y, z })
    }
    return points
  }

  if (scenario.arcMode === 'phased') {
    const phaseOrbitSMA = scenario.phaseOrbitSMA
    const phasePeriod = orbitalPeriod(phaseOrbitSMA)
    const phaseEcc = 0
    const phaseSteps = Math.floor(steps * 0.45)
    const mainSteps = steps - phaseSteps
    const phaseStepDur = phasePeriod * 1.5 / phaseSteps
    const phasePoints = []
    const n = Math.sqrt(GM / Math.pow(phaseOrbitSMA, 3))
    const M0 = kestrelElements.meanAnomaly0
    for (let i = 0; i <= phaseSteps; i++) {
      const t = i * phaseStepDur
      const M = ((M0 + n * t) % TWO_PI + TWO_PI) % TWO_PI
      const E = solveKepler(M, 0)
      const nu = M
      const [x, y, z] = keplerToECI(phaseOrbitSMA, phaseEcc, inc, raan, 0, nu)
      phasePoints.push({ t: startOffset + t, x, y, z })
    }
    const phaseEnd = phasePoints[phasePoints.length - 1].t
    const mainPoints = propagateTransferOrbit(phaseOrbitSMA, r2, raan, inc, phaseEnd, mainSteps)
    return [...phasePoints, ...mainPoints]
  }

  return propagateTransferOrbit(r1, r2, raan, inc, startOffset, steps)
}

export const LAUNCH_SITES = [
  { id: 'ksc',           name: 'Kennedy Space Center (LC-39)',    lat: 28.573,  lon: -80.649,  country: 'USA' },
  { id: 'vandenberg',    name: 'Vandenberg SFB (SLC-4)',          lat: 34.742,  lon: -120.574, country: 'USA' },
  { id: 'cape-canaveral',name: 'Cape Canaveral SFS',              lat: 28.488,  lon: -80.577,  country: 'USA' },
  { id: 'baikonur',      name: 'Baikonur Cosmodrome',             lat: 45.965,  lon: 63.305,   country: 'Kazakhstan' },
  { id: 'plesetsk',      name: 'Plesetsk Cosmodrome',             lat: 62.925,  lon: 40.577,   country: 'Russia' },
  { id: 'kourou',        name: 'Guiana Space Centre (ELA-3)',     lat: 5.236,   lon: -52.769,  country: 'France/ESA' },
  { id: 'sriharikota',   name: 'Satish Dhawan (SHAR)',            lat: 13.733,  lon: 80.235,   country: 'India' },
  { id: 'jiuquan',       name: 'Jiuquan Launch Center (LC-43)',   lat: 40.958,  lon: 100.291,  country: 'China' },
  { id: 'wenchang',      name: 'Wenchang Space Launch Site',      lat: 19.614,  lon: 110.951,  country: 'China' },
  { id: 'tanegashima',   name: 'Tanegashima Space Center',        lat: 30.396,  lon: 130.975,  country: 'Japan' },
  { id: 'mahia',         name: 'Māhia Peninsula (LC-1)',          lat: -39.262, lon: 177.864,  country: 'New Zealand' },
]

export const ORBIT_PRESETS = [
  { id: 'leo',  label: 'LEO 500 km',  altitudeKm: 500,   incDeg: 51.6,  description: 'Low Earth Orbit — ISS-like inclination' },
  { id: 'sso',  label: 'SSO 550 km',  altitudeKm: 550,   incDeg: 97.6,  description: 'Sun-Synchronous Orbit — ideal for Earth observation' },
  { id: 'sso700', label: 'SSO 700 km', altitudeKm: 700,  incDeg: 98.2,  description: 'SSO at 700 km — extended coverage swath' },
  { id: 'polar',label: 'Polar 600 km',altitudeKm: 600,   incDeg: 90.0,  description: 'Polar orbit — full Earth coverage' },
  { id: 'meo',  label: 'MEO 8000 km', altitudeKm: 8000,  incDeg: 55.0,  description: 'Medium Earth Orbit — navigation/comms' },
  { id: 'geo',  label: 'GEO 35786 km',altitudeKm: 35786, incDeg: 0.0,   description: 'Geostationary orbit — fixed ground track' },
]

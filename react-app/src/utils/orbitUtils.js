const GM = 3.986004418e14
const RE = 6.3781e6
const TWO_PI = 2 * Math.PI
const J2 = 1.08263e-3

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

/**
 * Propagate the actual Hohmann transfer ellipse starting at Kestrel's Burn 1
 * position and ending at the target's circular orbit altitude.
 *
 * The transfer ellipse is in Kestrel's orbital plane (inc, raan). Its periapsis
 * is at Kestrel's Burn 1 ECI position; its apoapsis is at targetSma radius.
 * True anomaly sweeps from 0 → π (periapsis → apoapsis) over the half-period.
 *
 * For coplanar scenarios (inc_diff ≈ 0) the arc end lands exactly on the
 * target orbit.  For inclined cases the arc correctly shows the altitude
 * change in Kestrel's plane — the plane-change cost shown separately explains
 * why an additional maneuver is needed.
 *
 * @param {object} kElsBurn  - Kestrel elements advanced to burn1_epoch
 * @param {number} targetSma - Target circular orbit SMA in metres
 * @param {number} steps     - Arc resolution (default 150)
 * @returns {{ points: Array<{t,x,y,z}>, transferSecs: number }}
 */
export function propagateHohmannArc(kElsBurn, targetSma, steps = 150) {
  const M0  = kElsBurn.meanAnomaly0
  const e_k = kElsBurn.ecc
  const E0  = solveKepler(M0, e_k)
  const nu0 = Math.atan2(Math.sqrt(1 - e_k * e_k) * Math.sin(E0), Math.cos(E0) - e_k)

  const p_k    = kElsBurn.sma * (1 - e_k * e_k)
  const r_peri = p_k / (1 + e_k * Math.cos(nu0))
  const r_apo  = targetSma

  const a_t = (r_peri + r_apo) / 2
  const e_t = Math.abs(r_apo - r_peri) / (r_apo + r_peri)
  const n_t = Math.sqrt(GM / Math.pow(a_t, 3))
  const transferSecs = Math.PI / n_t

  const argPerigee_t = ((kElsBurn.argPerigee + nu0) % TWO_PI + TWO_PI) % TWO_PI
  const ascending    = r_apo >= r_peri

  const points = []
  for (let i = 0; i <= steps; i++) {
    const nu  = (i / steps) * Math.PI * (ascending ? 1 : -1)
    const E   = 2 * Math.atan2(
      Math.sqrt(1 - e_t) * Math.sin(nu / 2),
      Math.sqrt(1 + e_t) * Math.cos(nu / 2)
    )
    const M   = E - e_t * Math.sin(E)
    const t   = Math.abs(M) / n_t
    const [x, y, z] = keplerToECI(a_t, e_t, kElsBurn.inc, kElsBurn.raan, argPerigee_t, nu)
    points.push({ t, x, y, z })
  }

  const last = points[points.length - 1]
  points.push({ t: last.t + 1, x: last.x, y: last.y, z: last.z })
  return { points, transferSecs }
}

export function propagateInterceptArc(kElsBurn, tElsBurn, transferSecs, steps = 150) {
  return propagateHohmannArc(kElsBurn, tElsBurn.sma, steps).points
}

export function propagateTransferOrbit(r1, r2, raan, incKestrel, startSeconds, steps = 100, burnArgPerigee = 0) {
  const at = (r1 + r2) / 2
  const ecc = Math.abs(r2 - r1) / (r1 + r2)
  // For ascending: burn is at periapsis — periapsis points toward burn direction
  // For descending: burn is at apoapsis — periapsis is π away from burn direction
  const argPerigee = r1 < r2
    ? burnArgPerigee
    : ((burnArgPerigee + Math.PI) % TWO_PI)
  const transferTime = Math.PI * Math.sqrt(Math.pow(at, 3) / GM)
  const n = Math.sqrt(GM / Math.pow(at, 3))
  // Ascending: start at periapsis (M=0); Descending: start at apoapsis (M=π)
  const M0 = r1 < r2 ? 0 : Math.PI
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
      multiplier: 300,
      range: 'CLAMPED',
      step: 'SYSTEM_CLOCK_MULTIPLIER',
    },
  }

  const entities = satellites.map((sat) => {
    const cartesian = []
    for (const pt of sat.points) {
      cartesian.push(pt.t, pt.x, pt.y, pt.z)
    }

    // availStartSec / availEndSec are seconds relative to startIso
    const availStart = sat.availStartSec !== undefined
      ? new Date(startMs + sat.availStartSec * 1000).toISOString()
      : startIso
    const availEnd = sat.availEndSec !== undefined
      ? new Date(startMs + sat.availEndSec * 1000).toISOString()
      : endIso

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
      label: sat.noLabel ? { show: false, text: '' } : {
        text: sat.label,
        font: '13pt sans-serif',
        fillColor: { rgba: [255, 255, 255, 220] },
        outlineColor: { rgba: [0, 0, 0, 160] },
        outlineWidth: 2,
        style: 'FILL_AND_OUTLINE',
        verticalOrigin: 'BOTTOM',
        pixelOffset: { cartesian2: [sat.labelOffsetX || 0, sat.labelOffsetY !== undefined ? sat.labelOffsetY : -14] },
        show: true,
      },
    }
  })

  return [doc, ...entities]
}

export function computeManeuverScenarios(r1, r2) {
  const base = hohmannTransfer(r1, r2)
  const burnWindow = computeOptimalBurnWindow(r1, r2)

  const s1 = {
    id: 'hohmann',
    name: 'Hohmann Transfer',
    tag: 'OPTIMAL',
    tagColor: '#3fb950',
    desc: 'Two-burn minimum-energy coplanar transfer. Wait for phase alignment, then execute two impulsive burns. Exact physics — minimum ΔV for any coplanar transfer.',
    dv1: base.dv1,
    dv2: base.dv2,
    dvTotal: base.dvTotal,
    transferTime: base.transferTime,
    waitTime: burnWindow.synodicPeriod / 2,
    at: base.at,
    ecc: Math.abs(r2 - r1) / (r1 + r2),
    arcMode: 'hohmann',
  }

  // Fast Intercept: overshoot/undershoot transfer orbit
  // Ascending: raise apoapsis 50% past target altitude → reach target on ascending leg (faster)
  // Descending: lower perigee 50% below target altitude → reach target on descending leg (faster)
  const ascending = r1 < r2
  const altDiff = Math.abs(r2 - r1)
  const overshoot = altDiff * 0.5
  const r_far = ascending ? r2 + overshoot : r1
  const r_near = ascending ? r1 : Math.max(RE + 220e3, r2 - overshoot)
  const at_fast = (r_far + r_near) / 2
  const ecc_fast = (r_far - r_near) / (r_far + r_near)
  const p_fast = at_fast * (1 - ecc_fast * ecc_fast)
  const n_fast = Math.sqrt(GM / Math.pow(at_fast, 3))

  const v1_circ = Math.sqrt(GM / r1)
  const v1_trans = Math.sqrt(GM * (2 / r1 - 1 / at_fast))
  const dv1_fast = Math.abs(v1_trans - v1_circ)

  const cos_nu_fast = (p_fast / r2 - 1) / ecc_fast
  let s2
  if (Math.abs(cos_nu_fast) <= 1 && at_fast > RE + 150e3) {
    const nu_arrive = ascending
      ? Math.acos(Math.max(-1, Math.min(1, cos_nu_fast)))
      : TWO_PI - Math.acos(Math.max(-1, Math.min(1, cos_nu_fast)))
    const E_arrive = 2 * Math.atan2(
      Math.sqrt(1 - ecc_fast) * Math.sin(nu_arrive / 2),
      Math.sqrt(1 + ecc_fast) * Math.cos(nu_arrive / 2)
    )
    const M_arrive = ((E_arrive - ecc_fast * Math.sin(E_arrive)) % TWO_PI + TWO_PI) % TWO_PI
    const M_start_fast = ascending ? 0 : Math.PI
    const transferTime_fast = ((M_arrive - M_start_fast + TWO_PI) % TWO_PI) / n_fast

    // Circularization ΔV: accounts for radial velocity component at r2
    const v_tot_r2 = Math.sqrt(GM * (2 / r2 - 1 / at_fast))
    const h_fast = Math.sqrt(GM * p_fast)
    const v_tang_r2 = h_fast / r2
    const v_rad_r2 = Math.sqrt(Math.max(0, v_tot_r2 * v_tot_r2 - v_tang_r2 * v_tang_r2))
    const v2_circ = Math.sqrt(GM / r2)
    const dv2_fast = Math.sqrt((v2_circ - v_tang_r2) ** 2 + v_rad_r2 ** 2)

    const pctFaster = Math.round((1 - transferTime_fast / base.transferTime) * 100)
    const pctMoreDv = Math.round(((dv1_fast + dv2_fast) / base.dvTotal - 1) * 100)

    s2 = {
      id: 'fast',
      name: 'Fast Intercept',
      tag: 'FAST',
      tagColor: '#e6b454',
      desc: `${ascending ? 'Overshoot' : 'Undershoot'} transfer — ${ascending ? 'apoapsis raised' : 'perigee lowered'} 50% past target altitude. ~${pctFaster}% faster transit, ~${pctMoreDv}% more ΔV. No phase wait.`,
      dv1: dv1_fast,
      dv2: dv2_fast,
      dvTotal: dv1_fast + dv2_fast,
      transferTime: transferTime_fast,
      waitTime: 0,
      at: at_fast,
      ecc: ecc_fast,
      nu_arrive,
      arcMode: 'fast',
    }
  } else {
    s2 = {
      ...s1,
      id: 'fast',
      name: 'Fast Intercept',
      tag: 'FAST',
      tagColor: '#e6b454',
      desc: 'Direct transfer (orbit geometry limits overshoot for this altitude difference).',
      waitTime: 0,
      arcMode: 'hohmann',
    }
  }

  // Phased Rendezvous: same ΔV as Hohmann — execute at the NEXT optimal window
  // In reality a phased rendezvous uses identical burns to Hohmann; the "phasing"
  // refers to waiting for the correct relative geometry, not a different maneuver.
  const s3 = {
    id: 'phased',
    name: 'Phased Rendezvous',
    tag: 'NEXT WINDOW',
    tagColor: '#58a6ff',
    desc: 'Execute the standard Hohmann transfer at the NEXT optimal alignment window (after one full synodic period). Identical ΔV to Hohmann — choose this if the primary window was missed.',
    dv1: base.dv1,
    dv2: base.dv2,
    dvTotal: base.dvTotal,
    transferTime: base.transferTime,
    waitTime: burnWindow.synodicPeriod * 1.5,
    at: base.at,
    ecc: Math.abs(r2 - r1) / (r1 + r2),
    arcMode: 'hohmann',
  }

  return [s1, s2, s3]
}

function raanDriftRate(sma, inc) {
  const n = Math.sqrt(GM / Math.pow(sma, 3))
  return -(3 / 2) * J2 * n * Math.pow(RE / sma, 2) * Math.cos(inc)
}

export function computeJ2RAANScenario(kestrelElements, targetElements) {
  const { sma: sma1, inc: inc1, raan: raan1 } = kestrelElements
  const { sma: sma2, inc: inc2, raan: raan2 } = targetElements

  let dRaan = raan2 - raan1
  while (dRaan > Math.PI) dRaan -= TWO_PI
  while (dRaan < -Math.PI) dRaan += TWO_PI
  const dRaanDeg = Math.abs(dRaan) * (180 / Math.PI)

  if (dRaanDeg < 1.0) return null

  const rate1 = raanDriftRate(sma1, inc1)
  const rate2 = raanDriftRate(sma2, inc2)
  const naturalDiffRate = rate1 - rate2

  let driftSMA = sma1
  let dvDriftOrbit = 0
  let diffRate = naturalDiffRate
  let useNatural = true

  if (dRaan * naturalDiffRate <= 0 || Math.abs(naturalDiffRate) < 1e-13) {
    const candidates = [200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 1000, 1200, 1500, 2000, 3000]
      .map((h) => RE + h * 1e3)
    let bestRate = 0
    let bestSMA = null
    for (const aSMA of candidates) {
      const rd = raanDriftRate(aSMA, inc1) - rate2
      if (dRaan * rd > 0 && Math.abs(rd) > Math.abs(bestRate)) {
        bestRate = rd
        bestSMA = aSMA
      }
    }
    if (!bestSMA) return null
    driftSMA = bestSMA
    diffRate = bestRate
    useNatural = false
    const toDrift = hohmannTransfer(sma1, driftSMA)
    const fromDrift = hohmannTransfer(driftSMA, sma1)
    dvDriftOrbit = toDrift.dvTotal + fromDrift.dvTotal
  }

  const waitTime = Math.abs(dRaan / diffRate)
  const base = hohmannTransfer(sma1, sma2)
  const driftAltKm = Math.round((driftSMA - RE) / 1e3)

  const desc = useNatural
    ? `Park at ${driftAltKm} km — natural J2 nodal precession passively closes the ${dRaanDeg.toFixed(1)}° RAAN gap. No plane-change burn. ΔV equals a standard Hohmann.`
    : `Transfer to ${driftAltKm} km drift orbit — J2 precession at this altitude closes the ${dRaanDeg.toFixed(1)}° RAAN gap faster than the parking orbit. Extra ΔV replaces costly in-plane burns.`

  return {
    id: 'j2raan',
    name: 'J2 RAAN Alignment',
    tag: 'LOW ΔV',
    tagColor: '#a78bfa',
    desc,
    dv1: base.dv1,
    dv2: base.dv2,
    dvTotal: base.dvTotal + dvDriftOrbit,
    transferTime: base.transferTime,
    waitTime,
    driftSMA,
    driftAltKm,
    dRaanDeg,
    at: base.at,
    ecc: Math.abs(sma2 - sma1) / (sma1 + sma2),
    arcMode: 'hohmann',
  }
}

export function propagateScenarioArc(scenario, kestrelElements, r2, steps = 150) {
  const { sma: r1, raan, inc, meanAnomaly0, ecc: parkEcc = 0 } = kestrelElements
  const waitTime = scenario.waitTime || 0

  // Kestrel's true anomaly at burn time (for circular parking orbit, nu ≈ M exactly when ecc=0)
  const n_park = Math.sqrt(GM / Math.pow(r1, 3))
  const M_burn = ((meanAnomaly0 + n_park * waitTime) % TWO_PI + TWO_PI) % TWO_PI
  const E_burn = solveKepler(M_burn, parkEcc)
  const sqrtE = Math.sqrt(Math.max(0, 1 - parkEcc * parkEcc))
  const nu_burn = Math.atan2(sqrtE * Math.sin(E_burn), Math.cos(E_burn) - parkEcc)
  const burnArgPerigee = ((nu_burn % TWO_PI) + TWO_PI) % TWO_PI

  if (scenario.arcMode === 'hohmann') {
    return propagateTransferOrbit(r1, r2, raan, inc, waitTime, steps, burnArgPerigee)
  }

  if (scenario.arcMode === 'fast') {
    const { at, ecc, nu_arrive } = scenario
    if (!at || !ecc || nu_arrive === undefined) {
      return propagateTransferOrbit(r1, r2, raan, inc, waitTime, steps, burnArgPerigee)
    }
    const ascending = r1 < r2
    const argPerigee = ascending ? burnArgPerigee : ((burnArgPerigee + Math.PI) % TWO_PI)
    const n = Math.sqrt(GM / Math.pow(at, 3))
    const M_start = ascending ? 0 : Math.PI
    const E_arrive = 2 * Math.atan2(
      Math.sqrt(1 - ecc) * Math.sin(nu_arrive / 2),
      Math.sqrt(1 + ecc) * Math.cos(nu_arrive / 2)
    )
    const M_arrive = ((E_arrive - ecc * Math.sin(E_arrive)) % TWO_PI + TWO_PI) % TWO_PI
    const transferTime = ((M_arrive - M_start + TWO_PI) % TWO_PI) / n
    const stepDur = transferTime / steps

    const points = []
    for (let i = 0; i <= steps; i++) {
      const t = i * stepDur
      const M = ((M_start + n * t) % TWO_PI + TWO_PI) % TWO_PI
      const E = solveKepler(M, ecc)
      const sqrtTerm = Math.sqrt(1 - ecc * ecc)
      const nu = Math.atan2(sqrtTerm * Math.sin(E), Math.cos(E) - ecc)
      const [x, y, z] = keplerToECI(at, ecc, inc, raan, argPerigee, nu)
      points.push({ t: waitTime + t, x, y, z })
    }
    return points
  }

  return propagateTransferOrbit(r1, r2, raan, inc, waitTime, steps, burnArgPerigee)
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

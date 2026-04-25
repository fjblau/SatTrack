import { useState, useEffect, useMemo } from 'react'
import './KestrelDataDials.css'

function healthColor(score) {
  if (score == null) return '#adb5bd'
  if (score >= 70) return '#27ae60'
  if (score >= 40) return '#f39c12'
  return '#e74c3c'
}

function fmtNum(v, decimals) {
  if (v == null) return null
  return v.toFixed(decimals)
}

function fmtSigned(v, decimals) {
  if (v == null) return null
  return (v >= 0 ? '+' : '') + v.toFixed(decimals)
}

function ValueCard({ label, value, unit, sub, color }) {
  return (
    <div className="kdd-card">
      <div className="kdd-label">{label}</div>
      <div className="kdd-big-value" style={{ color: color || '#2c3e50' }}>
        {value != null ? value : '—'}
        {value != null && unit && <span className="kdd-unit"> {unit}</span>}
      </div>
      {sub && <div className="kdd-sub">{sub}</div>}
    </div>
  )
}

function BoolCard({ label, value, trueColor = '#e74c3c', falseColor = '#27ae60' }) {
  const display = value == null ? '—' : value ? 'YES' : 'NO'
  const color = value == null ? '#adb5bd' : value ? trueColor : falseColor
  return (
    <div className="kdd-card">
      <div className="kdd-label">{label}</div>
      <div className="kdd-bool-dot" style={{ background: color }} />
      <div className="kdd-big-value" style={{ color }}>{display}</div>
    </div>
  )
}

const STATUS_COLORS = {
  nominal: '#27ae60',
  marginal: '#f1c40f',
  degraded: '#e67e22',
  anomalous: '#e74c3c',
  uncontrolled: '#c0392b',
  suspected_maneuver: '#e67e22',
  no_maneuver: '#27ae60',
}

function StatusCard({ label, value }) {
  const color = value != null ? (STATUS_COLORS[value] || '#adb5bd') : '#adb5bd'
  const display = value != null ? String(value).replace(/_/g, ' ') : '—'
  return (
    <div className="kdd-card">
      <div className="kdd-label">{label}</div>
      <div className="kdd-bool-dot" style={{ background: color }} />
      <div className="kdd-big-value" style={{ color, fontSize: '0.65rem' }}>{display}</div>
    </div>
  )
}

const CYCLE_MS = 3000

export default function KestrelDataDials({ observations, satelliteName, currentSimTime, obsWindowStart, obsWindowEnd }) {
  const sorted = useMemo(() => {
    if (!observations || !observations.length) return []
    return [...observations].sort((a, b) => {
      if (!a.observation_epoch) return 1
      if (!b.observation_epoch) return -1
      return a.observation_epoch.localeCompare(b.observation_epoch)
    })
  }, [observations])

  const [idx, setIdx] = useState(0)

  useEffect(() => {
    setIdx(0)
  }, [satelliteName])

  const simTimeMs = currentSimTime ? new Date(currentSimTime).getTime() : null
  const obsStartMs = obsWindowStart ? new Date(obsWindowStart).getTime() : null
  const obsEndMs = obsWindowEnd ? new Date(obsWindowEnd).getTime() : null
  const inObsWindow = simTimeMs != null && obsStartMs != null && obsEndMs != null
    && simTimeMs >= obsStartMs && simTimeMs <= obsEndMs

  const simDrivenIdx = useMemo(() => {
    if (!inObsWindow || !sorted.length || simTimeMs == null) return null
    let best = 0
    let bestDiff = Infinity
    for (let i = 0; i < sorted.length; i++) {
      const eMs = sorted[i].observation_epoch ? new Date(sorted[i].observation_epoch).getTime() : null
      if (eMs == null) continue
      const diff = Math.abs(eMs - simTimeMs)
      if (diff < bestDiff) { bestDiff = diff; best = i }
    }
    return best
  }, [inObsWindow, simTimeMs, sorted])

  useEffect(() => {
    if (simDrivenIdx != null) return
    if (sorted.length <= 1) return
    const id = setInterval(() => {
      setIdx(prev => (prev + 1) % sorted.length)
    }, CYCLE_MS)
    return () => clearInterval(id)
  }, [sorted.length, simDrivenIdx])

  const activeIdx = simDrivenIdx != null ? simDrivenIdx : idx

  if (!sorted.length) return null

  const latest = sorted[activeIdx]

  const health = latest.derived_health_score
  const mass = latest.estimated_mass_kg
  const spin = latest.spin_rate_rpm

  const att = latest.attitude || {}
  const th = latest.thermal || {}
  const mat = latest.material_signature || {}
  const prox = latest.proximity_state || {}
  const man = latest.maneuver_indicator || {}
  const decay = latest.orbital_decay_indicator || {}

  const roll_deg = latest.roll_deg ?? att.roll_deg ?? null
  const pitch_deg = latest.pitch_deg ?? att.pitch_deg ?? null
  const yaw_deg = latest.yaw_deg ?? att.yaw_deg ?? null
  const stability_flag = latest.stability_flag ?? att.stability_flag ?? null
  const surface_temp_K = latest.surface_temp_K ?? th.surface_temp_K ?? null
  const anomaly_flag = th.anomaly_flag ?? null
  const reflectivity_index = latest.reflectivity_index ?? mat.reflectivity_index ?? null
  const inferred_material = latest.inferred_material ?? mat.inferred_material ?? null
  const material_confidence = latest.material_confidence ?? mat.material_confidence ?? mat.confidence ?? null
  const range_km = latest.range_km ?? prox.range_km ?? null
  const relative_velocity_ms = latest.relative_velocity_ms ?? prox.relative_velocity_ms ?? null
  const delta_v_residual_ms = latest.delta_v_residual_ms ?? man.delta_v_residual_ms ?? null
  const maneuver_confidence = latest.maneuver_confidence ?? man.maneuver_confidence ?? man.confidence ?? null
  const maneuver_flag = latest.maneuver_flag ?? man.flag ?? null
  const perigee_drift_km_per_day = latest.perigee_drift_km_per_day ?? decay.perigee_drift_km_per_day ?? null
  const estimated_perigee_km = latest.estimated_perigee_km ?? decay.estimated_perigee_km ?? null

  const observation_mode = latest.observation_mode ?? null
  const sensors_active = latest.sensors_active ?? null
  const illumination = latest.illumination ?? null
  const pass_id = latest.pass_id ?? null
  const frame_index = latest.frame_index ?? null

  const epoch = latest.observation_epoch
    ? new Date(latest.observation_epoch).toISOString().slice(0, 16).replace('T', ' ') + 'Z'
    : null

  const progress = sorted.length > 1 ? activeIdx / (sorted.length - 1) : 1

  return (
    <div className="kdd-strip">
      <div className="kdd-strip-inner">

        <ValueCard
          label="HEALTH"
          value={fmtNum(health, 1)}
          unit="%"
          color={healthColor(health)}
        />

        {observation_mode != null && (
          <ValueCard
            label="OBS MODE"
            value={String(observation_mode).replace(/_/g, ' ')}
            color="#2c3e50"
          />
        )}

        {illumination != null && (
          <ValueCard
            label="ILLUMINATION"
            value={String(illumination).replace(/_/g, ' ')}
            color="#e67e22"
          />
        )}

        {sensors_active != null && (
          <ValueCard
            label="SENSORS"
            value={String(sensors_active).replace(/_/g, ' ')}
            color="#2980b9"
          />
        )}

        <ValueCard
          label="ROLL"
          value={fmtNum(roll_deg, 2)}
          unit="°"
          color="#9b59b6"
        />

        <ValueCard
          label="PITCH"
          value={fmtNum(pitch_deg, 2)}
          unit="°"
          color="#3498db"
        />

        <ValueCard
          label="YAW"
          value={fmtNum(yaw_deg, 2)}
          unit="°"
          color="#1abc9c"
        />

        <StatusCard
          label="STABILITY"
          value={stability_flag}
        />

        <ValueCard
          label="TEMP"
          value={fmtNum(surface_temp_K, 1)}
          unit="K"
          color="#e67e22"
        />

        <BoolCard
          label="THERM. ANOM"
          value={anomaly_flag}
          trueColor="#e74c3c"
          falseColor="#27ae60"
        />

        <ValueCard
          label="REFLECTIVITY"
          value={fmtNum(reflectivity_index, 3)}
          color="#16a085"
        />

        <ValueCard
          label="MATERIAL"
          value={inferred_material?.replace(/_/g, ' ')}
          sub={material_confidence != null ? `conf ${(material_confidence * 100).toFixed(0)}%` : null}
          color="#2c3e50"
        />

        <ValueCard
          label="RANGE"
          value={fmtNum(range_km, 1)}
          unit="km"
          sub={relative_velocity_ms != null ? `${relative_velocity_ms.toFixed(2)} m/s rel.` : null}
          color="#2980b9"
        />

        <ValueCard
          label="ΔV RESIDUAL"
          value={fmtNum(delta_v_residual_ms, 4)}
          unit="m/s"
          color="#6c3483"
        />

        {maneuver_confidence != null && (
          <ValueCard
            label="MNV CONF"
            value={fmtNum(maneuver_confidence * 100, 1)}
            unit="%"
            color="#6c3483"
          />
        )}

        <StatusCard
          label="MANEUVER"
          value={maneuver_flag}
        />

        {spin != null && (
          <ValueCard
            label="SPIN"
            value={fmtNum(spin, 2)}
            unit="rpm"
            color="#2c3e50"
          />
        )}

        {mass != null && (
          <ValueCard
            label="MASS"
            value={mass.toFixed(0)}
            unit="kg"
            color="#2c3e50"
          />
        )}

        {perigee_drift_km_per_day != null && (
          <ValueCard
            label="PERIGEE DRIFT"
            value={fmtSigned(perigee_drift_km_per_day, 3)}
            unit="km/d"
            sub={estimated_perigee_km != null ? `est. ${estimated_perigee_km.toFixed(0)} km` : null}
            color={perigee_drift_km_per_day < -0.01 ? '#e74c3c' : '#27ae60'}
          />
        )}

        {pass_id != null && (
          <ValueCard
            label="PASS ID"
            value={String(pass_id)}
            sub={frame_index != null ? `frame ${frame_index}` : null}
            color="#adb5bd"
          />
        )}

      </div>
      <div className="kdd-footer">
        {inObsWindow && <span className="kdd-obs-window-badge">● IN OBS WINDOW</span>}
        {epoch && <span className="kdd-epoch">obs {activeIdx + 1}/{sorted.length} · {epoch}</span>}
        {sorted.length > 1 && (
          <div className="kdd-progress-bar">
            <div className="kdd-progress-fill" style={{ width: `${progress * 100}%` }} />
          </div>
        )}
      </div>
    </div>
  )
}

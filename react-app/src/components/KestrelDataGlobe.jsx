import { useEffect, useRef, useState, useMemo } from 'react'
import './KestrelDataGlobe.css'

const CESIUM_VERSION = '1.122'
const CESIUM_BASE_URL = `https://cesium.com/downloads/cesiumjs/releases/${CESIUM_VERSION}/Build/Cesium`
const CESIUM_JS_URL = `${CESIUM_BASE_URL}/Cesium.js`
const CESIUM_CSS_URL = `${CESIUM_BASE_URL}/Widgets/widgets.css`

const GM = 3.986004418e14

let cesiumLoadPromise = null

function loadCesium() {
  if (cesiumLoadPromise) return cesiumLoadPromise
  cesiumLoadPromise = new Promise((resolve, reject) => {
    if (window.Cesium) { resolve(window.Cesium); return }
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = CESIUM_CSS_URL
    document.head.appendChild(link)
    const script = document.createElement('script')
    script.src = CESIUM_JS_URL
    script.onload = () => resolve(window.Cesium)
    script.onerror = () => reject(new Error('Failed to load CesiumJS from CDN'))
    document.head.appendChild(script)
  })
  return cesiumLoadPromise
}

function healthClass(score) {
  if (score == null) return 'unknown'
  if (score >= 70) return 'good'
  if (score >= 40) return 'warning'
  return 'critical'
}

function fmtDeg(rad) {
  const deg = rad * (180 / Math.PI)
  return (deg >= 0 ? '+' : '') + deg.toFixed(2) + '°'
}

function fmtAlt(m) {
  return (m / 1000).toFixed(1) + ' km'
}

function orbitalVelocity(altM) {
  const r = 6.3781e6 + altM
  return Math.sqrt(GM / r) / 1000
}

function fmtSimTime(julianDate) {
  try {
    const iso = window.Cesium.JulianDate.toIso8601(julianDate, 0)
    const d = new Date(iso)
    return d.toUTCString().replace('GMT', 'UTC').replace(/.*?,\s*/, '').replace(/:\d\d UTC/, ' UTC')
  } catch {
    return '—'
  }
}

function getCartographic(Cesium, entity, time) {
  try {
    const pos = entity.position.getValue(time)
    if (!pos) return null
    return Cesium.Cartographic.fromCartesian(pos)
  } catch {
    return null
  }
}

function flattenObservations(observations) {
  const rows = []
  for (const obs of observations) {
    const epoch = obs.observation_epoch
      ? new Date(obs.observation_epoch).toISOString().slice(0, 16).replace('T', ' ') + 'Z'
      : null

    const push = (label, value, highlight) => {
      if (value == null || value === '') return
      rows.push({ label, value: typeof value === 'number' ? value.toFixed(3) : String(value), epoch, highlight })
    }

    push('Source', obs.source)
    push('Health', obs.derived_health_score, true)
    push('Mass (kg)', obs.estimated_mass_kg)
    push('Spin (rpm)', obs.spin_rate_rpm)

    const att = obs.attitude
    if (att) {
      push('Roll (°)', att.roll_deg)
      push('Pitch (°)', att.pitch_deg)
      push('Yaw (°)', att.yaw_deg)
      push('Stability', att.stability_flag)
    }
    const th = obs.thermal
    if (th) {
      push('Temp (K)', th.surface_temp_K)
      push('Temp var 30d', th.temp_variance_30d)
      push('Thermal anomaly', th.anomaly_flag)
    }
    const mat = obs.material_signature
    if (mat) {
      push('Reflectivity', mat.reflectivity_index)
      push('Material', mat.inferred_material)
      push('Mat. confidence', mat.confidence)
    }
    const prox = obs.proximity_state
    if (prox) {
      push('Range (km)', prox.range_km)
      push('Rel. velocity (m/s)', prox.relative_velocity_ms)
    }
    const man = obs.maneuver_indicator
    if (man) {
      push('ΔV residual (m/s)', man.delta_v_residual_ms)
      push('Man. confidence', man.confidence)
      push('Man. flag', man.flag)
    }
    const decay = obs.orbital_decay_indicator
    if (decay) {
      push('Perigee drift (km/d)', decay.perigee_drift_km_per_day)
      push('Est. perigee (km)', decay.estimated_perigee_km)
    }
  }
  return rows
}

function ObservationTicker({ rows, satelliteName }) {
  const VISIBLE = 10
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    if (!rows.length) return
    const id = setInterval(() => {
      setOffset(prev => (prev + 1) % rows.length)
    }, 1200)
    return () => clearInterval(id)
  }, [rows.length])

  useEffect(() => {
    setOffset(0)
  }, [satelliteName])

  if (!rows.length) return null

  const visible = []
  for (let i = 0; i < VISIBLE; i++) {
    visible.push(rows[(offset + i) % rows.length])
  }

  return (
    <div className="kdg-ticker">
      <div className="kdg-ticker-header">
        <span className="kdg-ticker-dot" />
        LIVE OBSERVATION DATA
      </div>
      <div className="kdg-ticker-rows">
        {visible.map((row, i) => (
          <div
            key={i}
            className={`kdg-ticker-row${i === 0 ? ' kdg-ticker-row-entering' : ''}${row.highlight ? ' kdg-ticker-row-highlight' : ''}`}
          >
            <span className="kdg-ticker-label">{row.label}</span>
            <span className="kdg-ticker-value">{row.value}</span>
          </div>
        ))}
      </div>
      {rows[offset]?.epoch && (
        <div className="kdg-ticker-epoch">epoch {rows[offset].epoch}</div>
      )}
    </div>
  )
}

export default function KestrelDataGlobe({ czmlData, observations, satelliteName, healthScore, loading, emptyMessage }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const lastTickRef = useRef(0)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const [telemetry, setTelemetry] = useState(null)

  const tickerRows = useMemo(() => flattenObservations(observations || []), [observations])

  useEffect(() => {
    if (!czmlData || czmlData.length < 2) {
      setTelemetry(null)
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.dataSources.removeAll()
        viewerRef.current.entities.removeAll()
      }
      return
    }

    let destroyed = false

    const init = async () => {
      setStatus('loading')
      setError(null)
      setTelemetry(null)

      try {
        const Cesium = await loadCesium()
        if (destroyed) return

        if (viewerRef.current && !viewerRef.current.isDestroyed()) {
          viewerRef.current.destroy()
          viewerRef.current = null
        }

        if (!containerRef.current) return

        Cesium.Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN || ''

        const viewer = new Cesium.Viewer(containerRef.current, {
          terrainProvider: new Cesium.EllipsoidTerrainProvider(),
          baseLayerPicker: false,
          geocoder: false,
          homeButton: true,
          sceneModePicker: true,
          navigationHelpButton: false,
          animation: true,
          timeline: true,
          fullscreenButton: false,
          baseLayer: Cesium.ImageryLayer.fromProviderAsync(
            Cesium.ArcGisMapServerImageryProvider.fromUrl(
              'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer',
              { enablePickFeatures: false }
            )
          ),
        })

        viewerRef.current = viewer

        const dataSource = new Cesium.CzmlDataSource()
        await dataSource.load(czmlData)
        viewer.dataSources.add(dataSource)

        const clock = viewer.clock
        const docClock = czmlData[0]?.clock
        if (docClock?.interval) {
          const parts = docClock.interval.split('/')
          if (parts.length === 2) {
            clock.startTime = Cesium.JulianDate.fromIso8601(parts[0])
            clock.stopTime = Cesium.JulianDate.fromIso8601(parts[1])
            clock.currentTime = clock.startTime.clone()
            clock.clockRange = Cesium.ClockRange.LOOP_STOP
            clock.multiplier = 300
            clock.shouldAnimate = true
          }
        }

        viewer.timeline.zoomTo(clock.startTime, clock.stopTime)

        const entities = dataSource.entities.values
        if (entities.length > 0) {
          viewer.zoomTo(dataSource.entities, new Cesium.HeadingPitchRange(0, -Math.PI / 3, 12000000))
        }

        const tickListener = (clock) => {
          if (destroyed) return
          const now = Date.now()
          if (now - lastTickRef.current < 500) return
          lastTickRef.current = now

          const time = clock.currentTime
          const allEntities = dataSource.entities.values
          if (!allEntities.length) return

          const entity = allEntities[0]
          const carto = getCartographic(Cesium, entity, time)
          if (carto) {
            setTelemetry({
              lat: fmtDeg(carto.latitude),
              lon: fmtDeg(carto.longitude),
              alt: fmtAlt(carto.height),
              vel: orbitalVelocity(carto.height).toFixed(2) + ' km/s',
              simTime: fmtSimTime(time),
            })
          }
        }

        viewer.clock.onTick.addEventListener(tickListener)
        setStatus('ready')
      } catch (err) {
        if (!destroyed) {
          setError(err.message)
          setStatus('error')
        }
      }
    }

    init()

    return () => {
      destroyed = true
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy()
        viewerRef.current = null
      }
    }
  }, [czmlData])

  const hc = healthClass(healthScore)

  return (
    <div className="kdg-wrapper">
      {(!czmlData || czmlData.length < 2) && status !== 'loading' && (
        <div className="kdg-empty">
          {loading
            ? <><div className="kdg-spinner" /><p>Fetching orbital data…</p></>
            : <><div className="kdg-empty-icon">🛰</div><p>{emptyMessage || 'Select an object to visualise.'}</p></>
          }
        </div>
      )}
      {status === 'loading' && (
        <div className="kdg-status">
          <div className="kdg-spinner" />
          <p>Rendering orbital track…</p>
        </div>
      )}
      {status === 'error' && (
        <div className="kdg-status kdg-error">
          <p>Globe error: {error}</p>
          <p className="kdg-hint">CesiumJS loads from CDN — check your internet connection.</p>
        </div>
      )}

      <div
        ref={containerRef}
        className="kdg-container"
        style={{ visibility: status === 'ready' ? 'visible' : 'hidden' }}
      />

      {status === 'ready' && telemetry && (
        <div className="kdg-overlay">
          <div className="kdg-telemetry-card">
            <div className="kdg-telem-header">{satelliteName || 'SATELLITE'}</div>
            <div className="kdg-telem-rows">
              <div className="kdg-telem-row"><span>LAT</span><strong>{telemetry.lat}</strong></div>
              <div className="kdg-telem-row"><span>LON</span><strong>{telemetry.lon}</strong></div>
              <div className="kdg-telem-row"><span>ALT</span><strong>{telemetry.alt}</strong></div>
              <div className="kdg-telem-row"><span>VEL</span><strong>{telemetry.vel}</strong></div>
            </div>
            {healthScore != null && (
              <div className="kdg-health-bar-wrap">
                <div className="kdg-health-label">HEALTH {healthScore.toFixed(1)}</div>
                <div className="kdg-health-bar">
                  <div
                    className={`kdg-health-fill ${hc}`}
                    style={{ width: `${Math.min(100, Math.max(0, healthScore))}%` }}
                  />
                </div>
              </div>
            )}
            <div className="kdg-telem-time">{telemetry.simTime}</div>
          </div>
        </div>
      )}

      {status === 'ready' && tickerRows.length > 0 && (
        <ObservationTicker rows={tickerRows} satelliteName={satelliteName} />
      )}

      {status === 'ready' && (
        <div className="kdg-legend">
          <div className="kdg-legend-items">
            <div className="kdg-legend-item"><div className={`kdg-legend-dot ${hc}`} /> {satelliteName}</div>
          </div>
        </div>
      )}
    </div>
  )
}

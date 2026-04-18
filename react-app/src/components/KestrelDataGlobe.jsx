import { useEffect, useRef, useState } from 'react'
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

function healthColor(score) {
  if (score == null) return [139, 155, 180, 220]
  if (score >= 70) return [39, 174, 96, 255]
  if (score >= 40) return [243, 156, 18, 255]
  return [231, 76, 60, 255]
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

export default function KestrelDataGlobe({ czmlData, focusedSatId, emptyMessage }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const lastTickRef = useRef(0)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const [activeTelemetry, setActiveTelemetry] = useState(null)

  useEffect(() => {
    if (!czmlData || czmlData.length < 2) {
      setActiveTelemetry(null)
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.dataSources.removeAll()
      }
      return
    }

    let destroyed = false

    const init = async () => {
      setStatus('loading')
      setError(null)
      setActiveTelemetry(null)

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
          viewer.zoomTo(
            dataSource.entities,
            new Cesium.HeadingPitchRange(0, -Math.PI / 3, 20000000)
          )
        }

        const tickListener = (clock) => {
          if (destroyed) return
          const now = Date.now()
          if (now - lastTickRef.current < 500) return
          lastTickRef.current = now

          const time = clock.currentTime
          const allEntities = dataSource.entities.values
          const watchId = viewer._kdg_focusedId

          for (const entity of allEntities) {
            if (entity.id === watchId) {
              const carto = getCartographic(Cesium, entity, time)
              if (carto) {
                setActiveTelemetry({
                  name: entity.name || entity.id,
                  lat: fmtDeg(carto.latitude),
                  lon: fmtDeg(carto.longitude),
                  alt: fmtAlt(carto.height),
                  vel: orbitalVelocity(carto.height).toFixed(2) + ' km/s',
                  simTime: fmtSimTime(time),
                  healthScore: entity._kdg_healthScore,
                })
              }
              break
            }
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

  useEffect(() => {
    if (!viewerRef.current || viewerRef.current.isDestroyed()) return
    const viewer = viewerRef.current
    viewer._kdg_focusedId = focusedSatId || null

    if (!focusedSatId) {
      setActiveTelemetry(null)
      return
    }

    const dataSources = viewer.dataSources
    for (let i = 0; i < dataSources.length; i++) {
      const ds = dataSources.get(i)
      const entity = ds.entities.getById(focusedSatId)
      if (entity) {
        const Cesium = window.Cesium
        if (Cesium) {
          viewer.zoomTo(entity, new Cesium.HeadingPitchRange(0, -Math.PI / 4, 8000000))
        }
        break
      }
    }
  }, [focusedSatId])

  const score = activeTelemetry?.healthScore
  const hClass = healthClass(score)

  return (
    <div className="kdg-wrapper">
      {(!czmlData || czmlData.length < 2) && status !== 'loading' && (
        <div className="kdg-empty">
          <div className="kdg-empty-icon">🛰</div>
          <p>{emptyMessage || 'Fetching satellite data…'}</p>
        </div>
      )}
      {status === 'loading' && (
        <div className="kdg-status">
          <div className="kdg-spinner" />
          <p>Loading CesiumJS and rendering observed objects…</p>
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

      {status === 'ready' && activeTelemetry && (
        <div className="kdg-overlay">
          <div className="kdg-telemetry-card">
            <div className="kdg-telem-header">{activeTelemetry.name}</div>
            <div className="kdg-telem-rows">
              <div className="kdg-telem-row"><span>LAT</span><strong>{activeTelemetry.lat}</strong></div>
              <div className="kdg-telem-row"><span>LON</span><strong>{activeTelemetry.lon}</strong></div>
              <div className="kdg-telem-row"><span>ALT</span><strong>{activeTelemetry.alt}</strong></div>
              <div className="kdg-telem-row"><span>VEL</span><strong>{activeTelemetry.vel}</strong></div>
            </div>
            {score != null && (
              <div className="kdg-health-bar-wrap">
                <div className="kdg-health-label">HEALTH SCORE {score.toFixed(1)}</div>
                <div className="kdg-health-bar">
                  <div
                    className={`kdg-health-fill ${hClass}`}
                    style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                  />
                </div>
              </div>
            )}
            <div className="kdg-telem-time">{activeTelemetry.simTime}</div>
          </div>
        </div>
      )}

      {status === 'ready' && (
        <div className="kdg-legend">
          <div className="kdg-legend-title">Health Score</div>
          <div className="kdg-legend-items">
            <div className="kdg-legend-item"><div className="kdg-legend-dot good" /> ≥ 70 — Healthy</div>
            <div className="kdg-legend-item"><div className="kdg-legend-dot warning" /> 40–70 — Degraded</div>
            <div className="kdg-legend-item"><div className="kdg-legend-dot critical" /> &lt; 40 — Critical</div>
            <div className="kdg-legend-item"><div className="kdg-legend-dot unknown" /> No data</div>
          </div>
        </div>
      )}
    </div>
  )
}

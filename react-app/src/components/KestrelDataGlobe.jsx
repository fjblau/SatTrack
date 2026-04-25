import { useEffect, useRef, useState, useCallback } from 'react'
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

function fmtTimeLabel(ms) {
  const d = new Date(ms)
  const mo = d.toUTCString().replace(/.*?,\s*/, '').split(' ')
  return `${mo[0]} ${mo[1]} ${mo[2]}`
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

function ObsTimeline({ windowStart, windowEnd, obsStart, obsEnd, currentTime, onSeek }) {
  const barRef = useRef(null)

  if (!windowStart || !windowEnd) return null

  const wsMs = new Date(windowStart).getTime()
  const weMs = new Date(windowEnd).getTime()
  const osMs = obsStart ? new Date(obsStart).getTime() : null
  const oeMs = obsEnd ? new Date(obsEnd).getTime() : null
  const ctMs = currentTime ? new Date(currentTime).getTime() : null
  const totalMs = weMs - wsMs

  const frac = (ms) => Math.max(0, Math.min(1, (ms - wsMs) / totalMs))
  const obsStartFrac = osMs != null ? frac(osMs) : null
  const obsEndFrac = oeMs != null ? frac(oeMs) : null
  const curFrac = ctMs != null ? frac(ctMs) : null
  const inObs = ctMs != null && osMs != null && oeMs != null && ctMs >= osMs && ctMs <= oeMs

  const handleClick = (e) => {
    if (!barRef.current || !onSeek) return
    const rect = barRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const f = Math.max(0, Math.min(1, x / rect.width))
    onSeek(new Date(wsMs + f * totalMs).toISOString())
  }

  return (
    <div className="kdg-tl-wrap">
      <div className="kdg-tl-header">
        <span className="kdg-tl-title">OBSERVATION TIMELINE</span>
        {inObs && <span className="kdg-tl-in-obs">● IN OBS WINDOW</span>}
      </div>
      <div className="kdg-tl-bar" ref={barRef} onClick={handleClick} title="Click to seek">
        <div className="kdg-tl-bg" />
        {obsStartFrac != null && obsEndFrac != null && (
          <div
            className="kdg-tl-obs-band"
            style={{ left: `${obsStartFrac * 100}%`, width: `${(obsEndFrac - obsStartFrac) * 100}%` }}
          >
            <span className="kdg-tl-obs-label">OBS WINDOW</span>
          </div>
        )}
        {curFrac != null && (
          <div className="kdg-tl-cursor" style={{ left: `${curFrac * 100}%` }} />
        )}
      </div>
      <div className="kdg-tl-labels">
        <span>{fmtTimeLabel(wsMs)}</span>
        {obsStartFrac != null && (
          <span className="kdg-tl-label-obs" style={{ left: `${obsStartFrac * 100}%` }}>
            ▲ obs start
          </span>
        )}
        {obsEndFrac != null && (
          <span className="kdg-tl-label-obs" style={{ left: `${obsEndFrac * 100}%` }}>
            ▲ obs end
          </span>
        )}
        <span>{fmtTimeLabel(weMs)}</span>
      </div>
    </div>
  )
}

export default function KestrelDataGlobe({ czmlData, satelliteName, healthScore, loading, emptyMessage, windowStart, windowEnd, obsWindowStart, obsWindowEnd, onTimeChange }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const lastTickRef = useRef(0)
  const onTimeChangeRef = useRef(onTimeChange)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const [telemetry, setTelemetry] = useState(null)
  const [currentTimeIso, setCurrentTimeIso] = useState(null)

  useEffect(() => { onTimeChangeRef.current = onTimeChange }, [onTimeChange])

  const handleSeek = useCallback((isoTime) => {
    if (viewerRef.current && !viewerRef.current.isDestroyed() && window.Cesium) {
      viewerRef.current.clock.currentTime = window.Cesium.JulianDate.fromIso8601(isoTime)
      viewerRef.current.clock.shouldAnimate = false
    }
  }, [])

  useEffect(() => {
    if (!czmlData || czmlData.length < 2) {
      setTelemetry(null)
      setCurrentTimeIso(null)
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
      setCurrentTimeIso(null)

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

        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(0, 0, 22000000),
          orientation: { heading: 0, pitch: -Cesium.Math.PI_OVER_TWO, roll: 0 },
          duration: 0,
        })

        const tickListener = (clock) => {
          if (destroyed) return
          const now = Date.now()
          if (now - lastTickRef.current < 500) return
          lastTickRef.current = now

          const time = clock.currentTime
          const isoTime = Cesium.JulianDate.toIso8601(time)

          setCurrentTimeIso(isoTime)
          if (onTimeChangeRef.current) onTimeChangeRef.current(isoTime)

          const allEntities = dataSource.entities.values
          if (!allEntities.length) return

          const mainEntity = allEntities.find(e => e.id && !e.id.startsWith('sat-full-gray') && !e.id.startsWith('sat-obs-highlight')) || allEntities[0]
          const carto = getCartographic(Cesium, mainEntity, time)
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

      {status === 'ready' && (
        <div className="kdg-legend">
          <div className="kdg-legend-items">
            <div className="kdg-legend-item"><div className={`kdg-legend-dot ${hc}`} /> {satelliteName}</div>
            <div className="kdg-legend-item"><div className="kdg-legend-line kdg-legend-line-gray" /> Full Orbit Path</div>
            {obsWindowStart && <div className="kdg-legend-item"><div className="kdg-legend-line kdg-legend-line-obs" /> Observation Window</div>}
          </div>
        </div>
      )}

      {status === 'ready' && windowStart && windowEnd && (
        <ObsTimeline
          windowStart={windowStart}
          windowEnd={windowEnd}
          obsStart={obsWindowStart}
          obsEnd={obsWindowEnd}
          currentTime={currentTimeIso}
          onSeek={handleSeek}
        />
      )}
    </div>
  )
}

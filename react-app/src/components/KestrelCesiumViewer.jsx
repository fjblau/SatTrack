import { useEffect, useRef, useState } from 'react'
import './KestrelCesiumViewer.css'

const CESIUM_VERSION = '1.122'
const CESIUM_BASE_URL = `https://cesium.com/downloads/cesiumjs/releases/${CESIUM_VERSION}/Build/Cesium`
const CESIUM_JS_URL = `${CESIUM_BASE_URL}/Cesium.js`
const CESIUM_CSS_URL = `${CESIUM_BASE_URL}/Widgets/widgets.css`

const GM = 3.986004418e14

let cesiumLoadPromise = null

function loadCesium() {
  if (cesiumLoadPromise) return cesiumLoadPromise
  cesiumLoadPromise = new Promise((resolve, reject) => {
    if (window.Cesium) {
      resolve(window.Cesium)
      return
    }
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

function fmtDeg(rad) {
  const deg = rad * (180 / Math.PI)
  return (deg >= 0 ? '+' : '') + deg.toFixed(3) + '°'
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

export default function KestrelCesiumViewer({ czmlData, launchSite, emptyMessage, targetLabel }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const lastTickRef = useRef(0)
  const prevRangeRef = useRef(null)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const [kestrelTelemetry, setKestrelTelemetry] = useState(null)
  const [targetTelemetry, setTargetTelemetry] = useState(null)
  const [rangeTelemetry, setRangeTelemetry] = useState(null)

  useEffect(() => {
    if (!czmlData) {
      setKestrelTelemetry(null)
      setTargetTelemetry(null)
      setRangeTelemetry(null)
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.dataSources.removeAll()
        if (launchSite) {
          const Cesium = window.Cesium
          if (Cesium) {
            viewerRef.current.camera.flyTo({
              destination: Cesium.Cartesian3.fromDegrees(launchSite.lon, launchSite.lat, 8000000),
              duration: 1.5,
            })
          }
        }
      }
      return
    }

    let destroyed = false

    const init = async () => {
      setStatus('loading')
      setError(null)
      setKestrelTelemetry(null)
      setTargetTelemetry(null)
      setRangeTelemetry(null)

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

        if (launchSite) {
          viewer.entities.add({
            position: Cesium.Cartesian3.fromDegrees(launchSite.lon, launchSite.lat),
            point: {
              pixelSize: 12,
              color: Cesium.Color.ORANGE,
              outlineColor: Cesium.Color.WHITE,
              outlineWidth: 2,
              heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
            },
            label: {
              text: launchSite.name,
              font: '12pt sans-serif',
              fillColor: Cesium.Color.ORANGE,
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 2,
              style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
              pixelOffset: new Cesium.Cartesian2(0, -16),
            },
          })
        }

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
            clock.multiplier = 60
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
          const kestrelEntity = dataSource.entities.getById('kestrel')
          const targetEntity = dataSource.entities.getById('target')

          let kData = null
          let tData = null
          let rData = null

          if (kestrelEntity) {
            const carto = getCartographic(Cesium, kestrelEntity, time)
            if (carto) {
              kData = {
                lat: fmtDeg(carto.latitude),
                lon: fmtDeg(carto.longitude),
                alt: fmtAlt(carto.height),
                vel: orbitalVelocity(carto.height).toFixed(2) + ' km/s',
                simTime: fmtSimTime(time),
              }
            }
          }

          if (targetEntity) {
            const carto = getCartographic(Cesium, targetEntity, time)
            if (carto) {
              tData = {
                lat: fmtDeg(carto.latitude),
                lon: fmtDeg(carto.longitude),
                alt: fmtAlt(carto.height),
                vel: orbitalVelocity(carto.height).toFixed(2) + ' km/s',
              }
            }
          }

          if (kestrelEntity && targetEntity) {
            try {
              const kPos = kestrelEntity.position.getValue(time)
              const tPos = targetEntity.position.getValue(time)
              if (kPos && tPos) {
                const distM = Cesium.Cartesian3.distance(kPos, tPos)
                const distKm = distM / 1000
                let closingRate = null
                if (prevRangeRef.current !== null) {
                  closingRate = ((prevRangeRef.current - distKm) / 0.5).toFixed(2)
                }
                prevRangeRef.current = distKm
                rData = {
                  range: distKm >= 1000
                    ? (distKm / 1000).toFixed(2) + ' Mm'
                    : distKm.toFixed(1) + ' km',
                  closing: closingRate !== null
                    ? (parseFloat(closingRate) >= 0 ? '+' : '') + closingRate + ' km/s'
                    : '—',
                  closingPositive: closingRate !== null && parseFloat(closingRate) > 0,
                }
              }
            } catch {
            }
          }

          if (kData) setKestrelTelemetry(kData)
          if (tData) setTargetTelemetry(tData)
          if (rData) setRangeTelemetry(rData)
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
      prevRangeRef.current = null
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy()
        viewerRef.current = null
      }
    }
  }, [czmlData, launchSite])

  return (
    <div className="kcv-wrapper">
      {!czmlData && status !== 'loading' && (
        <div className="kcv-empty">
          <div className="kcv-empty-icon">🛰</div>
          <p>{emptyMessage || 'Configure mission parameters and click Compute Orbit to visualize.'}</p>
        </div>
      )}
      {status === 'loading' && (
        <div className="kcv-status">
          <div className="kcv-spinner" />
          <p>Loading CesiumJS and rendering orbit…</p>
        </div>
      )}
      {status === 'error' && (
        <div className="kcv-status kcv-error">
          <p>Globe error: {error}</p>
          <p className="kcv-hint">CesiumJS loads from CDN — check your internet connection.</p>
        </div>
      )}
      <div
        ref={containerRef}
        className="kcv-container"
        style={{ visibility: status === 'ready' ? 'visible' : 'hidden' }}
      />

      {kestrelTelemetry && (
        <div className="kcv-telemetry kcv-telemetry-left">
          <div className="kcv-telem-header kcv-telem-kestrel">KESTREL</div>
          <div className="kcv-telem-rows">
            <div className="kcv-telem-row"><span>LAT</span><strong>{kestrelTelemetry.lat}</strong></div>
            <div className="kcv-telem-row"><span>LON</span><strong>{kestrelTelemetry.lon}</strong></div>
            <div className="kcv-telem-row"><span>ALT</span><strong>{kestrelTelemetry.alt}</strong></div>
            <div className="kcv-telem-row"><span>VEL</span><strong>{kestrelTelemetry.vel}</strong></div>
          </div>
          {rangeTelemetry && (
            <div className="kcv-telem-range">
              <div className="kcv-telem-row">
                <span>RANGE</span>
                <strong>{rangeTelemetry.range}</strong>
              </div>
              <div className="kcv-telem-row">
                <span>CLOSING</span>
                <strong className={rangeTelemetry.closingPositive ? 'kcv-closing-in' : 'kcv-moving-away'}>
                  {rangeTelemetry.closing}
                </strong>
              </div>
            </div>
          )}
          <div className="kcv-telem-time">{kestrelTelemetry.simTime}</div>
        </div>
      )}

      {targetTelemetry && (
        <div className="kcv-telemetry kcv-telemetry-right">
          <div className="kcv-telem-header kcv-telem-target">{targetLabel || 'TARGET'}</div>
          <div className="kcv-telem-rows">
            <div className="kcv-telem-row"><span>LAT</span><strong>{targetTelemetry.lat}</strong></div>
            <div className="kcv-telem-row"><span>LON</span><strong>{targetTelemetry.lon}</strong></div>
            <div className="kcv-telem-row"><span>ALT</span><strong>{targetTelemetry.alt}</strong></div>
            <div className="kcv-telem-row"><span>VEL</span><strong>{targetTelemetry.vel}</strong></div>
          </div>
        </div>
      )}
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import './KestrelCesiumViewer.css'

const CESIUM_VERSION = '1.122'
const CESIUM_BASE_URL = `https://cesium.com/downloads/cesiumjs/releases/${CESIUM_VERSION}/Build/Cesium`
const CESIUM_JS_URL = `${CESIUM_BASE_URL}/Cesium.js`
const CESIUM_CSS_URL = `${CESIUM_BASE_URL}/Widgets/widgets.css`

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

export default function KestrelCesiumViewer({ czmlData, launchSite, emptyMessage }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!czmlData) {
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
    </div>
  )
}

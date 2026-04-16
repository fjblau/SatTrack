import { useEffect, useRef, useState } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import './CesiumViewer.css'

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

export default function CesiumViewer({ envelopeId, satelliteName }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!envelopeId) return

    let destroyed = false

    const init = async () => {
      setStatus('loading')
      setError(null)

      try {
        const Cesium = await loadCesium()

        if (destroyed) return

        const czmlRes = await apiFetch(API_ENDPOINTS.EPHEMERIS.CZML(envelopeId))
        if (!czmlRes.ok) {
          throw new Error(`Failed to fetch CZML: HTTP ${czmlRes.status}`)
        }
        const czml = await czmlRes.json()

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
          imageryProvider: new Cesium.OpenStreetMapImageryProvider({
            url: 'https://tile.openstreetmap.org/',
          }),
        })

        viewerRef.current = viewer

        const dataSource = new Cesium.CzmlDataSource()
        await dataSource.load(czml)
        viewer.dataSources.add(dataSource)

        const clock = viewer.clock
        if (czml[0]?.clock?.interval) {
          const parts = czml[0].clock.interval.split('/')
          if (parts.length === 2) {
            clock.startTime = Cesium.JulianDate.fromIso8601(parts[0])
            clock.stopTime = Cesium.JulianDate.fromIso8601(parts[1])
            clock.currentTime = clock.startTime.clone()
            clock.clockRange = Cesium.ClockRange.LOOP_STOP
            clock.multiplier = 60
          }
        }

        viewer.timeline.zoomTo(clock.startTime, clock.stopTime)

        const entities = dataSource.entities.values
        if (entities.length > 0) {
          viewer.trackedEntity = entities[0]
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
  }, [envelopeId])

  return (
    <div className="cesium-wrapper">
      {status === 'loading' && (
        <div className="cesium-status">
          <div className="cesium-spinner" />
          <p>Loading CesiumJS and ephemeris data…</p>
        </div>
      )}
      {status === 'error' && (
        <div className="cesium-status cesium-error">
          <p>Failed to load globe: {error}</p>
          <p className="cesium-hint">Check your internet connection (CesiumJS loads from CDN).</p>
        </div>
      )}
      <div
        ref={containerRef}
        className="cesium-container"
        style={{ visibility: status === 'ready' ? 'visible' : 'hidden' }}
      />
    </div>
  )
}

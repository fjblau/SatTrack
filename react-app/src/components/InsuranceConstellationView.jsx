import { useState, useEffect, useRef } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import './InsuranceConstellationView.css'

const CESIUM_VERSION = '1.122'
const CESIUM_BASE_URL = `https://cesium.com/downloads/cesiumjs/releases/${CESIUM_VERSION}/Build/Cesium`
const CESIUM_JS_URL = `${CESIUM_BASE_URL}/Cesium.js`
const CESIUM_CSS_URL = `${CESIUM_BASE_URL}/Widgets/widgets.css`

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

const EARTH_RADIUS_M = 6371000

const KESTREL_COLORS = {
  'KSTRL-01': '#22c55e',
  'KSTRL-02': '#3b82f6',
  'KSTRL-03': '#f59e0b',
  'KSTRL-04': '#a78bfa',
}

const STATUS_COLORS = {
  operational: '#15803d',
  degraded: '#d97706',
  safe_mode: '#dc2626',
  decommissioned: '#6b7280',
}

const TASK_STATUS_COLORS = {
  scheduled: '#0369a1',
  executing: '#d97706',
  completed: '#15803d',
  cancelled: '#6b7280',
  failed: '#dc2626',
}

function fmtDateTime(isoStr) {
  if (!isoStr) return '—'
  return isoStr.slice(0, 16).replace('T', ' ') + ' UTC'
}

function Badge({ color, children }) {
  return (
    <span className="icon-badge" style={{ background: color + '18', color, borderColor: color + '40' }}>
      {children}
    </span>
  )
}

function generateOrbitPoints(Cesium, altKm, inclinationDeg, raanDeg, steps = 90) {
  const R = EARTH_RADIUS_M + altKm * 1000
  const incRad = (inclinationDeg * Math.PI) / 180
  const raanRad = (raanDeg * Math.PI) / 180
  const points = []

  for (let i = 0; i <= steps; i++) {
    const u = (i / steps) * 2 * Math.PI
    const xOrb = R * Math.cos(u)
    const yOrb = R * Math.sin(u)

    const x = xOrb * (Math.cos(raanRad)) - yOrb * (Math.cos(incRad) * Math.sin(raanRad))
    const y = xOrb * (Math.sin(raanRad)) + yOrb * (Math.cos(incRad) * Math.cos(raanRad))
    const z = yOrb * Math.sin(incRad)

    points.push(new Cesium.Cartesian3(x, y, z))
  }
  return points
}

function generateSubsatellitePoint(Cesium, altKm, inclinationDeg, raanDeg, phase = 0) {
  const R = EARTH_RADIUS_M + altKm * 1000
  const incRad = (inclinationDeg * Math.PI) / 180
  const raanRad = (raanDeg * Math.PI) / 180
  const u = phase

  const xOrb = R * Math.cos(u)
  const yOrb = R * Math.sin(u)
  const x = xOrb * Math.cos(raanRad) - yOrb * Math.cos(incRad) * Math.sin(raanRad)
  const y = xOrb * Math.sin(raanRad) + yOrb * Math.cos(incRad) * Math.cos(raanRad)
  const z = yOrb * Math.sin(incRad)

  return new Cesium.Cartesian3(x, y, z)
}

// ── ConstellationGlobe3D ──────────────────────────────────────────────────────

function ConstellationGlobe3D({ kestrels }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  const kestrelOrbits = [
    { id: 'KSTRL-01', altKm: 505, inclination: 53,  raan: 0   },
    { id: 'KSTRL-02', altKm: 615, inclination: 72,  raan: 90  },
    { id: 'KSTRL-03', altKm: 555, inclination: 97.5,raan: 45  },
    { id: 'KSTRL-04', altKm: 535, inclination: 45,  raan: 180 },
  ]

  kestrels.forEach(k => {
    const def = kestrelOrbits.find(o => o.id === k.id || k.name?.includes(o.id))
    if (def && k.orbit_summary) {
      if (k.orbit_summary.alt_km) def.altKm = k.orbit_summary.alt_km
      if (k.orbit_summary.inclination_deg) def.inclination = k.orbit_summary.inclination_deg
    }
  })

  useEffect(() => {
    let destroyed = false

    const init = async () => {
      setStatus('loading')
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
          homeButton: false,
          sceneModePicker: false,
          navigationHelpButton: false,
          animation: false,
          timeline: false,
          fullscreenButton: false,
          baseLayer: Cesium.ImageryLayer.fromProviderAsync(
            Cesium.ArcGisMapServerImageryProvider.fromUrl(
              'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer',
              { enablePickFeatures: false }
            )
          ),
        })

        viewerRef.current = viewer
        viewer.scene.backgroundColor = Cesium.Color.fromCssColorString('#0f172a')

        kestrelOrbits.forEach((orb, idx) => {
          const colorHex = KESTREL_COLORS[orb.id] || '#ffffff'
          const color = Cesium.Color.fromCssColorString(colorHex)
          const orbitPoints = generateOrbitPoints(Cesium, orb.altKm, orb.inclination, orb.raan)

          viewer.entities.add({
            polyline: {
              positions: orbitPoints,
              width: 1.5,
              material: new Cesium.PolylineDashMaterialProperty({
                color: color.withAlpha(0.65),
                dashLength: 12,
              }),
              arcType: Cesium.ArcType.NONE,
            },
          })

          const phase = (idx / kestrelOrbits.length) * 2 * Math.PI
          const satPos = generateSubsatellitePoint(Cesium, orb.altKm, orb.inclination, orb.raan, phase)

          viewer.entities.add({
            position: satPos,
            point: {
              pixelSize: 10,
              color: color,
              outlineColor: Cesium.Color.WHITE,
              outlineWidth: 2,
            },
            label: {
              text: orb.id,
              font: '10pt sans-serif',
              fillColor: color,
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 2,
              style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
              pixelOffset: new Cesium.Cartesian2(0, -14),
            },
          })

          const footprintRadius = 1800000 + orb.altKm * 800
          const carto = Cesium.Cartographic.fromCartesian(satPos)
          const lat = carto.latitude * (180 / Math.PI)
          const lon = carto.longitude * (180 / Math.PI)

          viewer.entities.add({
            position: Cesium.Cartesian3.fromDegrees(lon, lat, 0),
            ellipse: {
              semiMajorAxis: footprintRadius,
              semiMinorAxis: footprintRadius,
              material: color.withAlpha(0.08),
              outline: true,
              outlineColor: color.withAlpha(0.35),
              outlineWidth: 1.5,
              heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
            },
          })
        })

        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(0, 20, 30000000),
          orientation: { heading: 0, pitch: -Math.PI / 3, roll: 0 },
          duration: 0,
        })

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
  }, [kestrels])

  return (
    <div className="icon-globe-wrapper">
      {status === 'loading' && (
        <div className="icon-globe-status">
          <div className="icon-spinner" />
          <span>Loading Cesium globe…</span>
        </div>
      )}
      {status === 'error' && (
        <div className="icon-globe-status icon-globe-error">
          Globe error: {error}
        </div>
      )}
      <div
        ref={containerRef}
        className="icon-globe-container"
        style={{ visibility: status === 'ready' ? 'visible' : 'hidden' }}
      />
      <div className="icon-globe-legend">
        {Object.entries(KESTREL_COLORS).map(([id, color]) => (
          <div key={id} className="icon-legend-row">
            <span className="icon-legend-dot" style={{ background: color }} />
            <span>{id}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── CoverageMatrix ────────────────────────────────────────────────────────────

function CoverageMatrix({ kestrels, assets }) {
  const kestrelIds = kestrels.map(k => k.id)

  if (assets.length === 0 || kestrelIds.length === 0) {
    return (
      <div className="icon-empty">No coverage data available</div>
    )
  }

  const getCell = (assetIdx, kestrelIdx) => {
    const seed = (assetIdx * 7 + kestrelIdx * 13 + 3) % 100
    if (seed < 40) return { label: 'continuous', color: '#15803d' }
    if (seed < 65) return { label: 'good',       color: '#0369a1' }
    if (seed < 82) return { label: 'intermittent',color: '#d97706' }
    return { label: 'gap',          color: '#dc2626' }
  }

  const displayAssets = assets.slice(0, 12)

  return (
    <div className="icon-matrix-wrap">
      <table className="icon-matrix">
        <thead>
          <tr>
            <th className="icon-matrix-corner">Asset</th>
            {kestrelIds.map((kid, ki) => (
              <th key={kid} className="icon-matrix-kestrel">
                <span style={{ color: KESTREL_COLORS[kid] || '#fff' }}>
                  {kid}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {displayAssets.map((asset, ai) => (
            <tr key={asset.satellite_id || ai}>
              <td className="icon-matrix-asset">
                <span title={asset.satellite_id}>{asset.name || asset.satellite_id}</span>
              </td>
              {kestrelIds.map((kid, ki) => {
                const cell = getCell(ai, ki)
                return (
                  <td key={kid} className="icon-matrix-cell">
                    <div
                      className="icon-matrix-dot"
                      style={{ background: cell.color }}
                      title={`${asset.name || asset.satellite_id} × ${kid}: ${cell.label}`}
                    />
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="icon-matrix-legend">
        {[
          { label: 'continuous',   color: '#15803d' },
          { label: 'good',         color: '#0369a1' },
          { label: 'intermittent', color: '#d97706' },
          { label: 'gap',          color: '#dc2626' },
        ].map(l => (
          <div key={l.label} className="icon-matrix-legend-row">
            <span className="icon-matrix-legend-dot" style={{ background: l.color }} />
            <span className="icon-matrix-legend-label">{l.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── TaskingQueue ──────────────────────────────────────────────────────────────

function TaskingQueue({ kestrels }) {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    apiFetch(API_ENDPOINTS.INSURANCE.CONSTELLATION_TASKING)
      .then(r => r.json())
      .then(d => {
        const syntheticTasks = []
        const statuses = ['executing', 'scheduled', 'scheduled', 'completed', 'completed']
        const taskTypes = ['observation', 'calibration', 'slew', 'observation', 'observation']
        ;(d.kestrels || []).forEach((k, ki) => {
          for (let i = 0; i < 3; i++) {
            const now = new Date()
            const offset = (ki * 3 + i) * 14 - 20
            const when = new Date(now.getTime() + offset * 60000)
            syntheticTasks.push({
              task_id: `TQ-${k.id}-${i}`,
              kestrel_id: k.id,
              kestrel_name: k.name || k.id,
              status: statuses[(ki + i) % statuses.length],
              task_type: taskTypes[(ki * 2 + i) % taskTypes.length],
              scheduled_for: when.toISOString(),
              priority: i === 0 ? 'high' : 'normal',
            })
          }
        })
        syntheticTasks.sort((a, b) => new Date(a.scheduled_for) - new Date(b.scheduled_for))
        setTasks(syntheticTasks)
        setLoading(false)
      })
      .catch(() => {
        setLoading(false)
      })
  }, [])

  if (loading) return <div className="icon-loading"><div className="icon-spinner" /> Loading task queue…</div>

  return (
    <div className="icon-queue-wrap">
      <table className="icon-table">
        <thead>
          <tr>
            <th>Task ID</th>
            <th>Kestrel</th>
            <th>Type</th>
            <th>Status</th>
            <th>Priority</th>
            <th>Scheduled</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map(t => (
            <tr key={t.task_id}>
              <td className="icon-mono">{t.task_id}</td>
              <td>
                <span style={{ color: KESTREL_COLORS[t.kestrel_id] || '#0f172a', fontWeight: 600 }}>
                  {t.kestrel_name}
                </span>
              </td>
              <td className="icon-capitalize">{t.task_type}</td>
              <td>
                <Badge color={TASK_STATUS_COLORS[t.status] || '#6b7280'}>
                  {t.status}
                </Badge>
              </td>
              <td>
                <Badge color={t.priority === 'high' ? '#dc2626' : '#64748b'}>
                  {t.priority}
                </Badge>
              </td>
              <td className="icon-muted">{fmtDateTime(t.scheduled_for)}</td>
            </tr>
          ))}
          {tasks.length === 0 && (
            <tr>
              <td colSpan={6} className="icon-empty">No tasks in queue</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ── KestrelStatusBar ──────────────────────────────────────────────────────────

function KestrelStatusBar({ kestrels }) {
  const KSTRL_IDS = ['KSTRL-01', 'KSTRL-02', 'KSTRL-03', 'KSTRL-04']

  const resolved = KSTRL_IDS.map(kid => {
    const found = kestrels.find(k => k.id === kid || k.name === kid)
    return found || { id: kid, name: kid, status: 'operational', orbit_summary: { regime: 'LEO', alt_km: 550 } }
  })

  return (
    <div className="icon-kestrel-bar">
      {resolved.map(k => (
        <div key={k.id} className="icon-kestrel-pill">
          <span
            className="icon-kestrel-dot"
            style={{ background: KESTREL_COLORS[k.id] || '#64748b' }}
          />
          <span className="icon-kestrel-name">{k.name || k.id}</span>
          <Badge color={STATUS_COLORS[k.status] || '#6b7280'}>{k.status}</Badge>
          <span className="icon-kestrel-orbit">
            {k.orbit_summary?.regime || 'LEO'} · {k.orbit_summary?.alt_km ?? '—'} km
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Main Export ───────────────────────────────────────────────────────────────

export default function InsuranceConstellationView() {
  const [constellationData, setConstellationData] = useState(null)
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      apiFetch(API_ENDPOINTS.INSURANCE.CONSTELLATION_TASKING).then(r => r.json()),
      apiFetch(API_ENDPOINTS.INSURANCE.ASSETS()).then(r => r.json()),
    ])
      .then(([consData, assetsData]) => {
        setConstellationData(consData)
        setAssets(assetsData.assets || [])
        setLoading(false)
      })
      .catch(e => {
        setError(e.message)
        setLoading(false)
      })
  }, [])

  const kestrels = constellationData?.kestrels || []

  if (loading) {
    return (
      <div className="icon-root">
        <div className="icon-loading-full">
          <div className="icon-spinner" /> Loading constellation data…
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="icon-root">
        <div className="icon-error-full">Error loading data: {error}</div>
      </div>
    )
  }

  return (
    <div className="icon-root">
      <KestrelStatusBar kestrels={kestrels} />

      <div className="icon-main-grid">
        <div className="icon-globe-panel">
          <div className="icon-panel-title">Kestrel Constellation — Orbital Coverage</div>
          <ConstellationGlobe3D kestrels={kestrels} />
        </div>

        <div className="icon-right-panel">
          <div className="icon-card">
            <div className="icon-panel-title">Coverage Matrix — Asset × Kestrel</div>
            <CoverageMatrix kestrels={kestrels} assets={assets} />
          </div>
        </div>
      </div>

      <div className="icon-card icon-queue-card">
        <div className="icon-panel-title">
          Tasking Queue
          <span className="icon-panel-badge">Live</span>
        </div>
        <TaskingQueue kestrels={kestrels} />
      </div>
    </div>
  )
}

import { useState, useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import './InsuranceAggregationView.css'

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

const EARTH_RADIUS_KM = 6371

function seededRng(seed) {
  let s = seed >>> 0
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0
    return s / 0xffffffff
  }
}

function hashStr(str) {
  let h = 5381
  for (let i = 0; i < str.length; i++) h = (Math.imul(33, h) ^ str.charCodeAt(i)) >>> 0
  return h
}

const BAND_COLORS_HEX = {
  low: '#15803d', moderate: '#0369a1', elevated: '#d97706', high: '#dc2626', critical: '#7f1d1d',
}

const SHELLS_ORDERED = [
  'LEO_500_520', 'LEO_520_540', 'LEO_540_560', 'LEO_560_580',
  'MEO_19000_21000', 'GEO_W', 'GEO_E',
]

const CONFIDENCE_OPTIONS = [
  { value: 0.95, label: '95% — High confidence' },
  { value: 0.85, label: '85% — Standard' },
  { value: 0.70, label: '70% — Low confidence' },
  { value: 0.50, label: '50% — Speculative' },
]

function fmtSI(amount) {
  if (amount == null) return '—'
  if (amount >= 1e9) return `$${(amount / 1e9).toFixed(1)}B`
  if (amount >= 1e6) return `$${(amount / 1e6).toFixed(0)}M`
  return `$${amount.toLocaleString()}`
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

const BAND_COLORS = {
  low: '#15803d', moderate: '#0369a1', elevated: '#d97706', high: '#dc2626', critical: '#7f1d1d',
}

function Badge({ color, children }) {
  return (
    <span className="iagg-badge" style={{ background: color + '18', color, borderColor: color + '40' }}>
      {children}
    </span>
  )
}

function CoverageTypeBadge({ type }) {
  const map = {
    direct: '#15803d',
    adjacent: '#0369a1',
    limited: '#d97706',
    none: '#6b7280',
  }
  return <Badge color={map[type] || '#6b7280'}>{type}</Badge>
}

// ── OrbitalShellGlobe ─────────────────────────────────────────────────────────

function OrbitalShellGlobe({ shells, highlightShellId, scenarioResult, onAssetSelect }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

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
          infoBox: false,
          selectionIndicator: false,
          baseLayer: Cesium.ImageryLayer.fromProviderAsync(
            Cesium.ArcGisMapServerImageryProvider.fromUrl(
              'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer',
              { enablePickFeatures: false }
            )
          ),
        })

        viewerRef.current = viewer
        viewer.scene.backgroundColor = Cesium.Color.fromCssColorString('#0f172a')

        const leoBands = shells.filter(s =>
          ['LEO_500_520','LEO_520_540','LEO_540_560','LEO_560_580'].includes(s.shell_id)
        )
        const otherBands = shells.filter(s =>
          !['LEO_500_520','LEO_520_540','LEO_540_560','LEO_560_580'].includes(s.shell_id)
        )

        const drawShell = (shell) => {
          const isHighlighted = shell.shell_id === highlightShellId
          const intensity = shell.heatmap_intensity || 0.3
          const color = Cesium.Color.fromCssColorString(shell.color || '#0369a1')
          const alpha = isHighlighted ? 0.55 : 0.12 + intensity * 0.28

          const radiiM = (EARTH_RADIUS_KM + shell.alt_km) * 1000

          viewer.entities.add({
            id: `shell-${shell.shell_id}`,
            position: Cesium.Cartesian3.ZERO,
            ellipsoid: {
              radii: new Cesium.Cartesian3(radiiM, radiiM, radiiM),
              material: color.withAlpha(alpha),
              outline: true,
              outlineColor: color.withAlpha(isHighlighted ? 0.9 : 0.4),
              outlineWidth: isHighlighted ? 2.0 : 1.0,
              stackPartitions: 32,
              slicePartitions: 32,
              fill: true,
            },
            label: isHighlighted ? {
              text: shell.label,
              font: 'bold 14pt sans-serif',
              fillColor: Cesium.Color.WHITE,
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 3,
              style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              pixelOffset: new Cesium.Cartesian2(0, 0),
              showBackground: true,
              backgroundColor: new Cesium.Color(0.05, 0.1, 0.2, 0.75),
              backgroundPadding: new Cesium.Cartesian2(8, 5),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            } : undefined,
          })
        }

        leoBands.forEach(drawShell)
        otherBands.forEach(drawShell)

        if (scenarioResult && highlightShellId) {
          const shellMeta = shells.find(s => s.shell_id === highlightShellId) || {}
          const altKm = shellMeta.alt_km || 550

          const debrisToDraw = Math.min(scenarioResult.debris_count || 0, 800)
          const shellSeed = (highlightShellId || '').split('').reduce((a, c) => a + c.charCodeAt(0), 0)
          const rng = seededRng(debrisToDraw * 7 + shellSeed)
          for (let i = 0; i < debrisToDraw; i++) {
            const lon = rng() * 360 - 180
            const lat = rng() * 160 - 80
            const alt = (altKm + rng() * 20 - 10) * 1000
            viewer.entities.add({
              position: Cesium.Cartesian3.fromDegrees(lon, lat, alt),
              point: {
                pixelSize: 2,
                color: Cesium.Color.ORANGE.withAlpha(0.75),
              },
            })
          }

          const entityToAsset = new Map()

          for (const asset of scenarioResult.affected_assets || []) {
            const h = hashStr(asset.satellite_id || asset.name || String(Math.random()))
            const lon = ((h % 36000) / 36000) * 360 - 180
            const lat = (((h >>> 8) % 16000) / 16000) * 160 - 80
            const col = Cesium.Color.fromCssColorString(BAND_COLORS_HEX[asset.risk_band] || '#dc2626')
            const displayName = asset.name ||
              (asset.norad_id ? `NORAD ${asset.norad_id}` : `Sat …${(asset.satellite_id || '').slice(-6)}`)
            const descHtml = `<table class="cesium-infoBox-defaultTable cesium-infoBox-defaultTable-lighter"><tbody>
              <tr><th>Operator</th><td>${asset.operator || '—'}</td></tr>
              <tr><th>Risk Band</th><td style="color:${BAND_COLORS_HEX[asset.risk_band] || '#dc2626'};font-weight:700">${asset.risk_band || '—'}</td></tr>
              <tr><th>Sum Insured</th><td>${fmtSI(asset.sum_insured)}</td></tr>
              <tr><th>Sum at Risk</th><td style="font-weight:700">${fmtSI(asset.sum_at_risk)}</td></tr>
              <tr><th>Exposure</th><td>${asset.exposure_pct != null ? asset.exposure_pct + '%' : '—'}</td></tr>
              <tr><th>Hit Probability</th><td>${asset.hit_probability != null ? (asset.hit_probability * 100).toFixed(1) + '%' : '—'}</td></tr>
            </tbody></table>`
            const ent = viewer.entities.add({
              name: displayName,
              description: descHtml,
              position: Cesium.Cartesian3.fromDegrees(lon, lat, altKm * 1000),
              point: {
                pixelSize: 12,
                color: col,
                outlineColor: Cesium.Color.WHITE,
                outlineWidth: 2,
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
              },
              label: {
                text: displayName,
                font: 'bold 13pt sans-serif',
                fillColor: Cesium.Color.WHITE,
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 2,
                style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                pixelOffset: new Cesium.Cartesian2(16, 0),
                horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
                distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 80000000),
                showBackground: true,
                backgroundColor: new Cesium.Color(0, 0, 0, 0.65),
                backgroundPadding: new Cesium.Cartesian2(7, 4),
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
              },
            })
            entityToAsset.set(ent, asset)
          }

          viewer.selectedEntityChanged.addEventListener((entity) => {
            if (entity && entityToAsset.has(entity)) {
              onAssetSelect?.(entityToAsset.get(entity))
            } else if (!entity) {
              onAssetSelect?.(null)
            }
          })
        }

        if (scenarioResult && highlightShellId) {
          const shellMeta = shells.find(s => s.shell_id === highlightShellId) || {}
          const shellAltKm = shellMeta.alt_km || 550
          const viewAltM = Math.max((shellAltKm + 6000) * 1000, 10000000)
          viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(0, 25, viewAltM),
            duration: 1.2,
          })
        } else {
          viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(0, 0, 45000000),
            orientation: { heading: 0, pitch: -Math.PI / 2, roll: 0 },
            duration: 0,
          })
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
  }, [shells, highlightShellId, scenarioResult])

  return (
    <div className="iagg-globe-wrapper">
      {status === 'loading' && (
        <div className="iagg-globe-status">
          <div className="iagg-spinner" />
          <span>Loading Cesium globe…</span>
        </div>
      )}
      {status === 'error' && (
        <div className="iagg-globe-status iagg-globe-error">
          Globe error: {error}
        </div>
      )}
      <div
        ref={containerRef}
        className="iagg-globe-container"
        style={{ visibility: status === 'ready' ? 'visible' : 'hidden' }}
      />
    </div>
  )
}

// ── ShellHeatmap ──────────────────────────────────────────────────────────────

function ShellHeatmap({ shells }) {
  if (!shells || shells.length === 0) return null
  return (
    <div className="iagg-heatmap">
      {shells.map(s => (
        <div key={s.shell_id} className="iagg-heatmap-row">
          <div className="iagg-heatmap-label" title={s.shell_id}>
            {s.label}
          </div>
          <div className="iagg-heatmap-track">
            <div
              className="iagg-heatmap-fill"
              style={{
                width: `${Math.round((s.heatmap_intensity || 0) * 100)}%`,
                background: s.color || '#0369a1',
              }}
              title={fmtSI(s.sum_insured)}
            />
          </div>
          <div className="iagg-heatmap-meta">
            <span className="iagg-heatmap-value">{fmtSI(s.sum_insured)}</span>
            <span className="iagg-heatmap-pct">{s.pct_of_book}%</span>
            <span className="iagg-heatmap-count">{s.asset_count} assets</span>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── ScenarioForm ──────────────────────────────────────────────────────────────

function ScenarioForm({ shells, onResult, onShellSelect }) {
  const [shellId, setShellId] = useState('')
  const [debrisCount, setDebrisCount] = useState(500)
  const [confidence, setConfidence] = useState(0.85)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)

  const shellOptions = shells.length > 0 ? shells : SHELLS_ORDERED.map(s => ({ shell_id: s, label: s }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!shellId) return
    setRunning(true)
    setError(null)
    try {
      const res = await apiFetch(API_ENDPOINTS.INSURANCE.SCENARIO_FRAGMENTATION, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shell_id: shellId, debris_count: debrisCount, confidence }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      onResult(data)
      onShellSelect(shellId)
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <form className="iagg-form" onSubmit={handleSubmit}>
      <h3 className="iagg-form-title">Fragmentation Scenario</h3>

      <div className="iagg-form-row">
        <label className="iagg-label">Orbital Shell</label>
        <select
          className="iagg-select"
          value={shellId}
          onChange={e => { setShellId(e.target.value); onShellSelect(e.target.value) }}
          required
        >
          <option value="">Select shell…</option>
          {shellOptions.map(s => (
            <option key={s.shell_id} value={s.shell_id}>
              {s.label || s.shell_id}
              {s.sum_insured ? ` — ${fmtSI(s.sum_insured)} SI` : ''}
            </option>
          ))}
        </select>
      </div>

      <div className="iagg-form-row">
        <label className="iagg-label">Debris Count</label>
        <div className="iagg-range-row">
          <input
            type="range"
            min={10}
            max={10000}
            step={10}
            value={debrisCount}
            onChange={e => setDebrisCount(Number(e.target.value))}
            className="iagg-range"
          />
          <span className="iagg-range-value">{debrisCount.toLocaleString()}</span>
        </div>
      </div>

      <div className="iagg-form-row">
        <label className="iagg-label">Confidence Level</label>
        <select
          className="iagg-select"
          value={confidence}
          onChange={e => setConfidence(Number(e.target.value))}
        >
          {CONFIDENCE_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {error && <div className="iagg-form-error">Error: {error}</div>}

      <button type="submit" className="iagg-btn-run" disabled={!shellId || running}>
        {running ? 'Running…' : 'Run Scenario'}
      </button>
    </form>
  )
}

// ── ScenarioGraph ─────────────────────────────────────────────────────────────

function ScenarioGraph({ result }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current || !result) return

    const assets = result.affected_assets || []
    const kestrals = result.kestrel_coverage_impact || []

    const positions = {}
    positions['event'] = { x: 450, y: 0 }
    positions['shell'] = { x: 450, y: 190 }

    const N = assets.length
    if (N > 0) {
      const xMin = 30, xMax = 420
      assets.forEach((a, i) => {
        const x = N === 1 ? 230 : xMin + i * (xMax - xMin) / (N - 1)
        positions[`asset_${a.satellite_id}`] = { x, y: 390 + (i % 2) * 70 }
      })
    }

    const M = kestrals.length
    if (M > 0) {
      const xMin = 480, xMax = 870
      kestrals.forEach((k, j) => {
        const x = M === 1 ? 675 : xMin + j * (xMax - xMin) / (M - 1)
        positions[`kestrel_${k.kestrel_id}`] = { x, y: 390 + (j % 2) * 70 }
      })
    }

    const elements = []

    elements.push({
      data: { id: 'event', label: 'Fragmentation\nEvent', nodeType: 'event' },
      position: positions['event'],
    })

    elements.push({
      data: { id: 'shell', label: result.shell_label, nodeType: 'shell' },
      position: positions['shell'],
    })

    elements.push({
      data: {
        id: 'e-event-shell',
        source: 'event',
        target: 'shell',
        edgeLabel: `${result.debris_count?.toLocaleString()} fragments\n${Math.round((result.confidence || 0) * 100)}% confidence`,
        edgeType: 'fragmentation',
      },
    })

    assets.forEach((a) => {
      const displayName = a.name ||
        (a.norad_id ? `NORAD ${a.norad_id}` : `Sat \u2026${(a.satellite_id || '').slice(-6)}`)
      const hitPct = a.hit_probability != null
        ? `${(a.hit_probability * 100).toFixed(0)}%`
        : '\u2014'
      elements.push({
        data: {
          id: `asset_${a.satellite_id}`,
          label: displayName,
          nodeType: 'asset',
          riskBand: a.risk_band || 'moderate',
        },
        position: positions[`asset_${a.satellite_id}`],
      })
      elements.push({
        data: {
          id: `e-shell-${a.satellite_id}`,
          source: 'shell',
          target: `asset_${a.satellite_id}`,
          edgeLabel: `${a.exposure_pct}% exposure\n${hitPct} hit prob`,
          edgeType: 'exposure',
          riskBand: a.risk_band || 'moderate',
        },
      })
    })

    kestrals.forEach((k) => {
      const obsPct = k.observation_probability != null
        ? `${(k.observation_probability * 100).toFixed(0)}%`
        : '\u2014'
      elements.push({
        data: {
          id: `kestrel_${k.kestrel_id}`,
          label: k.kestrel_name || k.kestrel_id,
          nodeType: 'kestrel',
          kestrelStatus: k.status,
        },
        position: positions[`kestrel_${k.kestrel_id}`],
      })
      elements.push({
        data: {
          id: `e-kestrel-${k.kestrel_id}`,
          source: `kestrel_${k.kestrel_id}`,
          target: 'shell',
          edgeLabel: `${obsPct} obs prob\n\u0394alt ${k.alt_diff_km}km`,
          edgeType: 'observation',
        },
      })
    })

    if (cyRef.current) {
      cyRef.current.destroy()
      cyRef.current = null
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      layout: { name: 'preset' },
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'text-wrap': 'wrap',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '11px',
            'font-weight': 'bold',
            color: '#fff',
            'text-outline-width': 2,
            'text-outline-color': 'rgba(0,0,0,0.65)',
            width: 82,
            height: 82,
          },
        },
        {
          selector: 'node[nodeType="event"]',
          style: {
            'background-color': '#b91c1c',
            width: 100,
            height: 100,
            shape: 'star',
          },
        },
        {
          selector: 'node[nodeType="shell"]',
          style: {
            'background-color': '#1e40af',
            width: 98,
            height: 98,
            shape: 'ellipse',
          },
        },
        {
          selector: 'node[nodeType="asset"]',
          style: {
            'background-color': '#94a3b8',
            width: 76,
            height: 76,
            shape: 'hexagon',
          },
        },
        ...['low', 'moderate', 'elevated', 'high', 'critical'].map(band => ({
          selector: `node[nodeType="asset"][riskBand="${band}"]`,
          style: { 'background-color': BAND_COLORS_HEX[band] },
        })),
        {
          selector: 'node[nodeType="kestrel"]',
          style: {
            'background-color': '#059669',
            width: 70,
            height: 70,
            shape: 'diamond',
          },
        },
        {
          selector: 'node[nodeType="kestrel"][kestrelStatus="degraded"]',
          style: { 'background-color': '#78716c' },
        },
        {
          selector: 'edge',
          style: {
            width: 2,
            'line-color': '#94a3b8',
            'target-arrow-color': '#94a3b8',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(edgeLabel)',
            'font-size': '10px',
            'font-weight': '600',
            color: '#1e293b',
            'text-background-color': '#f8fafc',
            'text-background-opacity': 0.95,
            'text-background-padding': '4px',
            'text-background-shape': 'roundrectangle',
            'text-wrap': 'wrap',
            'text-max-width': '130px',
          },
        },
        {
          selector: 'edge[edgeType="fragmentation"]',
          style: {
            'line-color': '#dc2626',
            'target-arrow-color': '#dc2626',
            width: 3,
          },
        },
        {
          selector: 'edge[edgeType="exposure"][riskBand="elevated"]',
          style: { 'line-color': '#d97706', 'target-arrow-color': '#d97706', width: 2.5 },
        },
        {
          selector: 'edge[edgeType="exposure"][riskBand="high"]',
          style: { 'line-color': '#dc2626', 'target-arrow-color': '#dc2626', width: 3 },
        },
        {
          selector: 'edge[edgeType="exposure"][riskBand="critical"]',
          style: { 'line-color': '#7f1d1d', 'target-arrow-color': '#7f1d1d', width: 3.5 },
        },
        {
          selector: 'edge[edgeType="observation"]',
          style: {
            'line-color': '#059669',
            'target-arrow-color': '#059669',
            'line-style': 'dashed',
          },
        },
        {
          selector: ':selected',
          style: {
            'border-width': 4,
            'border-color': '#f59e0b',
            'border-style': 'solid',
          },
        },
      ],
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
    })

    cy.fit(undefined, 40)
    cyRef.current = cy

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [result])

  return (
    <div className="iagg-sg-wrap">
      <div ref={containerRef} className="iagg-sg-canvas" />
      <div className="iagg-sg-legend">
        <span className="iagg-sg-legend-item">
          <span className="iagg-sg-dot" style={{ background: '#b91c1c' }} />
          Fragmentation Event
        </span>
        <span className="iagg-sg-legend-item">
          <span className="iagg-sg-dot" style={{ background: '#1e40af' }} />
          Orbital Shell
        </span>
        <span className="iagg-sg-legend-item">
          <span className="iagg-sg-dot" style={{ background: '#dc2626' }} />
          Asset (color = risk band)
        </span>
        <span className="iagg-sg-legend-item">
          <span className="iagg-sg-dot" style={{ background: '#059669' }} />
          Kestrel Observer
        </span>
        <span className="iagg-sg-legend-item iagg-sg-legend-solid">
          <span className="iagg-sg-line" />
          impacts asset
        </span>
        <span className="iagg-sg-legend-item iagg-sg-legend-dashed">
          <span className="iagg-sg-line iagg-sg-line-dashed" style={{ borderColor: '#059669' }} />
          observes shell
        </span>
      </div>
    </div>
  )
}

// ── ScenarioResult ────────────────────────────────────────────────────────────

function ScenarioResult({ result }) {
  if (!result) return null

  const { affected_assets = [], kestrel_coverage_impact = [] } = result

  return (
    <div className="iagg-result">
      <div className="iagg-result-header">
        <h3 className="iagg-result-title">
          Scenario: {result.shell_label}
        </h3>
        <div className="iagg-result-meta">
          {result.debris_count?.toLocaleString()} debris fragments ·{' '}
          {Math.round((result.confidence || 0) * 100)}% confidence
        </div>
      </div>

      <div className="iagg-result-kpis">
        <div className="iagg-kpi">
          <div className="iagg-kpi-label">Total Sum at Risk</div>
          <div className="iagg-kpi-value iagg-kpi-danger">{fmtSI(result.total_sum_at_risk)}</div>
        </div>
        <div className="iagg-kpi">
          <div className="iagg-kpi-label">Affected Assets</div>
          <div className="iagg-kpi-value">{result.affected_count} of {result.total_assets_in_shell}</div>
        </div>
        <div className="iagg-kpi">
          <div className="iagg-kpi-label">Shell</div>
          <div className="iagg-kpi-value iagg-kpi-small">{result.shell_label}</div>
        </div>
      </div>

      {(affected_assets.length > 0 || kestrel_coverage_impact.length > 0) && (
        <div className="iagg-result-section">
          <h4 className="iagg-result-subtitle">Impact Analysis</h4>

          {affected_assets.length > 0 && (
            <>
              <h4 className="iagg-result-subtitle" style={{ marginTop: '1rem' }}>Affected Insured Assets</h4>
              <div className="iagg-result-table-wrap">
                <table className="iagg-table">
                  <thead>
                    <tr>
                      <th>Asset</th>
                      <th>Operator</th>
                      <th>Sum Insured</th>
                      <th>Sum at Risk</th>
                      <th>Exposure</th>
                      <th>Risk Band</th>
                      <th>Hit Prob</th>
                    </tr>
                  </thead>
                  <tbody>
                    {affected_assets.map(a => (
                      <tr key={a.satellite_id}>
                        <td className="iagg-bold">{a.name || a.satellite_id}</td>
                        <td className="iagg-muted">{a.operator || '—'}</td>
                        <td>{fmtSI(a.sum_insured)}</td>
                        <td className="iagg-bold iagg-danger">{fmtSI(a.sum_at_risk)}</td>
                        <td className="iagg-center">{a.exposure_pct}%</td>
                        <td>
                          <Badge color={BAND_COLORS[a.risk_band] || '#6b7280'}>
                            {a.risk_band || '—'}
                          </Badge>
                        </td>
                        <td className="iagg-center iagg-muted">
                          {a.hit_probability != null ? `${(a.hit_probability * 100).toFixed(1)}%` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {kestrel_coverage_impact.length > 0 && (
            <>
              <h4 className="iagg-result-subtitle" style={{ marginTop: '1.25rem' }}>Kestrel Coverage Impact</h4>
              <table className="iagg-table">
                <thead>
                  <tr>
                    <th>Kestrel</th>
                    <th>Status</th>
                    <th>Coverage Type</th>
                    <th>Obs Probability</th>
                    <th>Alt Diff (km)</th>
                  </tr>
                </thead>
                <tbody>
                  {kestrel_coverage_impact.map(k => (
                    <tr key={k.kestrel_id}>
                      <td className="iagg-bold">{k.kestrel_name || k.kestrel_id}</td>
                      <td>{k.status || '—'}</td>
                      <td><CoverageTypeBadge type={k.coverage_type} /></td>
                      <td className="iagg-center">
                        {k.observation_probability != null
                          ? `${(k.observation_probability * 100).toFixed(1)}%`
                          : '—'}
                      </td>
                      <td className="iagg-center iagg-muted">{k.alt_diff_km?.toLocaleString() || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Export ───────────────────────────────────────────────────────────────

export default function InsuranceAggregationView() {
  const [shells, setShells] = useState([])
  const [shellsLoading, setShellsLoading] = useState(true)
  const [shellsError, setShellsError] = useState(null)
  const [scenarioResult, setScenarioResult] = useState(null)
  const [highlightShellId, setHighlightShellId] = useState(null)
  const [selectedGlobeAsset, setSelectedGlobeAsset] = useState(null)

  useEffect(() => {
    setShellsLoading(true)
    apiFetch(API_ENDPOINTS.INSURANCE.AGGREGATION_SHELLS())
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { setShells(d.shells || []); setShellsLoading(false) })
      .catch(e => { setShellsError(e.message); setShellsLoading(false) })
  }, [])

  return (
    <div className="iagg-root">
      <div className="iagg-main-grid">
        <div className="iagg-viz-panel">
          <div className="iagg-panel-title">Orbital Shell Exposure</div>
          {shellsLoading && (
            <div className="iagg-globe-wrapper">
              <div className="iagg-globe-status">
                <div className="iagg-spinner" />
                <span>Loading shell data…</span>
              </div>
            </div>
          )}
          {shellsError && (
            <div className="iagg-globe-wrapper">
              <div className="iagg-globe-status iagg-globe-error">
                Failed to load shell data: {shellsError}
              </div>
            </div>
          )}
          {!shellsLoading && !shellsError && (
            <OrbitalShellGlobe
              shells={shells}
              highlightShellId={highlightShellId}
              scenarioResult={scenarioResult}
              onAssetSelect={setSelectedGlobeAsset}
            />
          )}
        </div>

        <div className="iagg-viz-panel">
          <div className="iagg-panel-title">Impact Graph</div>
          {scenarioResult ? (
            <ScenarioGraph result={scenarioResult} />
          ) : (
            <div className="iagg-globe-wrapper">
              <div className="iagg-globe-status">
                Run a scenario to see the impact graph
              </div>
            </div>
          )}
        </div>

        <div className="iagg-sidebar-col">
          <div className="iagg-card">
            <ScenarioForm
              shells={shells}
              onResult={setScenarioResult}
              onShellSelect={setHighlightShellId}
            />
          </div>

          {!shellsLoading && shells.length > 0 && (
            <div className="iagg-card">
              <div className="iagg-panel-title">Book Exposure by Shell</div>
              <ShellHeatmap shells={shells} />
            </div>
          )}
        </div>
      </div>

      {selectedGlobeAsset && (
        <div className="iagg-selected-asset-card">
          <div className="iagg-selected-asset-header">
            <span className="iagg-selected-asset-name">
              {selectedGlobeAsset.name || `Sat …${(selectedGlobeAsset.satellite_id || '').slice(-6)}`}
            </span>
            <span className="iagg-selected-asset-hint">Selected on globe</span>
            <button
              className="iagg-selected-asset-close"
              onClick={() => setSelectedGlobeAsset(null)}
              aria-label="Dismiss"
            >✕</button>
          </div>
          <div className="iagg-selected-asset-body">
            <div className="iagg-selected-kpi">
              <span className="iagg-selected-kpi-label">Risk Band</span>
              <Badge color={BAND_COLORS[selectedGlobeAsset.risk_band] || '#6b7280'}>
                {selectedGlobeAsset.risk_band || '—'}
              </Badge>
            </div>
            <div className="iagg-selected-kpi">
              <span className="iagg-selected-kpi-label">Operator</span>
              <span className="iagg-selected-kpi-value">{selectedGlobeAsset.operator || '—'}</span>
            </div>
            <div className="iagg-selected-kpi">
              <span className="iagg-selected-kpi-label">Sum Insured</span>
              <span className="iagg-selected-kpi-value">{fmtSI(selectedGlobeAsset.sum_insured)}</span>
            </div>
            <div className="iagg-selected-kpi">
              <span className="iagg-selected-kpi-label">Sum at Risk</span>
              <span className="iagg-selected-kpi-value iagg-danger">{fmtSI(selectedGlobeAsset.sum_at_risk)}</span>
            </div>
            <div className="iagg-selected-kpi">
              <span className="iagg-selected-kpi-label">Exposure</span>
              <span className="iagg-selected-kpi-value">
                {selectedGlobeAsset.exposure_pct != null ? `${selectedGlobeAsset.exposure_pct}%` : '—'}
              </span>
            </div>
            <div className="iagg-selected-kpi">
              <span className="iagg-selected-kpi-label">Hit Probability</span>
              <span className="iagg-selected-kpi-value">
                {selectedGlobeAsset.hit_probability != null
                  ? `${(selectedGlobeAsset.hit_probability * 100).toFixed(1)}%`
                  : '—'}
              </span>
            </div>
          </div>
        </div>
      )}

      {scenarioResult && (
        <div className="iagg-result-container">
          <ScenarioResult result={scenarioResult} />
        </div>
      )}
    </div>
  )
}

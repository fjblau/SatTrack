import { useState, useEffect, useRef } from 'react'
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

function OrbitalShellGlobe({ shells, highlightShellId, scenarioResult }) {
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
              font: '11pt sans-serif',
              fillColor: Cesium.Color.WHITE,
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 2,
              style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              pixelOffset: new Cesium.Cartesian2(0, 0),
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

          for (const asset of scenarioResult.affected_assets || []) {
            const h = hashStr(asset.satellite_id || asset.name || String(Math.random()))
            const lon = ((h % 36000) / 36000) * 360 - 180
            const lat = (((h >>> 8) % 16000) / 16000) * 160 - 80
            const col = Cesium.Color.fromCssColorString(BAND_COLORS_HEX[asset.risk_band] || '#dc2626')
            viewer.entities.add({
              position: Cesium.Cartesian3.fromDegrees(lon, lat, altKm * 1000),
              point: {
                pixelSize: 10,
                color: col,
                outlineColor: Cesium.Color.WHITE,
                outlineWidth: 1.5,
              },
              label: {
                text: asset.name || asset.satellite_id,
                font: '9pt sans-serif',
                fillColor: Cesium.Color.WHITE,
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 2,
                style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                pixelOffset: new Cesium.Cartesian2(0, -16),
                distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 18000000),
              },
            })
          }
        }

        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(0, 0, 45000000),
          orientation: {
            heading: 0,
            pitch: -Math.PI / 2,
            roll: 0,
          },
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

      {affected_assets.length > 0 && (
        <div className="iagg-result-section">
          <h4 className="iagg-result-subtitle">Affected Insured Assets</h4>
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
        </div>
      )}

      {kestrel_coverage_impact.length > 0 && (
        <div className="iagg-result-section">
          <h4 className="iagg-result-subtitle">Kestrel Coverage Impact</h4>
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

  useEffect(() => {
    setShellsLoading(true)
    apiFetch(API_ENDPOINTS.INSURANCE.AGGREGATION_SHELLS())
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { setShells(d.shells || []); setShellsLoading(false) })
      .catch(e => { setShellsError(e.message); setShellsLoading(false) })
  }, [])

  return (
    <div className="iagg-root">
      <div className="iagg-top">
        <div className="iagg-globe-panel">
          <div className="iagg-panel-title">Orbital Shell Exposure</div>
          {shellsLoading && (
            <div className="iagg-globe-placeholder">
              <div className="iagg-spinner" /> Loading shell data…
            </div>
          )}
          {shellsError && (
            <div className="iagg-globe-placeholder iagg-error">
              Failed to load shell data: {shellsError}
            </div>
          )}
          {!shellsLoading && !shellsError && (
            <OrbitalShellGlobe shells={shells} highlightShellId={highlightShellId} scenarioResult={scenarioResult} />
          )}
        </div>

        <div className="iagg-sidebar">
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

      {scenarioResult && (
        <div className="iagg-result-container">
          <ScenarioResult result={scenarioResult} />
        </div>
      )}
    </div>
  )
}

import { useState, useMemo, useRef } from 'react'
import { TimeSeriesChart } from './ObservationDashboard'
import apiFetch from '../utils/apiFetch'
import './AdHocAnalytics.css'

const PRESET_COLORS = [
  '#3498db', '#e74c3c', '#27ae60', '#f39c12', '#9b59b6',
  '#1abc9c', '#e67e22', '#16a085', '#8e44ad', '#2c3e50',
  '#7f8c8d', '#6c3483', '#c0392b', '#2980b9', '#f1c40f',
]

let _seq = 0
function uid() { return `ah-${++_seq}-${Date.now().toString(36)}` }

function isValidEpoch(v) {
  if (v == null || String(v).trim() === '') return false
  const d = new Date(String(v).trim())
  if (!isNaN(d.getTime())) return true
  const n = Number(v)
  if (!isNaN(n) && n > 0) return true
  return false
}

function normalizeEpoch(v) {
  const s = String(v).trim()
  const d = new Date(s)
  if (!isNaN(d.getTime())) return d.toISOString()
  const n = Number(s)
  if (!isNaN(n) && n > 0) return new Date(n < 1e10 ? n * 1000 : n).toISOString()
  return s
}

function emptyMetric(colorIdx) {
  return { _id: uid(), key: '', label: '', color: PRESET_COLORS[colorIdx % PRESET_COLORS.length] }
}
function emptyFlag() {
  return { _id: uid(), key: '', trueLabel: '', trueColor: '#e74c3c', trueOnly: true, style: 'line' }
}
function emptyBand() {
  return { _id: uid(), min: '', max: '', color: '#3498db26' }
}

const STARTER_COLLECTION = [
  {
    "epoch": "2025-01-15T08:00:00Z",
    "signal_dbm": -68.2,
    "noise_floor_dbm": -97.4,
    "link_quality": 0.94,
    "anomaly_detected": false
  },
  {
    "epoch": "2025-01-15T09:00:00Z",
    "signal_dbm": -70.1,
    "noise_floor_dbm": -96.8,
    "link_quality": 0.91,
    "anomaly_detected": false
  },
  {
    "epoch": "2025-01-15T10:00:00Z",
    "signal_dbm": -73.6,
    "noise_floor_dbm": -95.2,
    "link_quality": 0.86,
    "anomaly_detected": false
  },
  {
    "epoch": "2025-01-15T11:00:00Z",
    "signal_dbm": -79.3,
    "noise_floor_dbm": -93.7,
    "link_quality": 0.72,
    "anomaly_detected": true
  },
  {
    "epoch": "2025-01-15T12:00:00Z",
    "signal_dbm": -84.5,
    "noise_floor_dbm": -92.1,
    "link_quality": 0.61,
    "anomaly_detected": true
  },
  {
    "epoch": "2025-01-15T13:00:00Z",
    "signal_dbm": -82.0,
    "noise_floor_dbm": -93.5,
    "link_quality": 0.65,
    "anomaly_detected": true
  },
  {
    "epoch": "2025-01-15T14:00:00Z",
    "signal_dbm": -76.4,
    "noise_floor_dbm": -95.0,
    "link_quality": 0.78,
    "anomaly_detected": false
  },
  {
    "epoch": "2025-01-15T15:00:00Z",
    "signal_dbm": -71.8,
    "noise_floor_dbm": -96.3,
    "link_quality": 0.88,
    "anomaly_detected": false
  },
  {
    "epoch": "2025-01-15T16:00:00Z",
    "signal_dbm": -69.5,
    "noise_floor_dbm": -97.1,
    "link_quality": 0.93,
    "anomaly_detected": false
  },
  {
    "epoch": "2025-01-15T17:00:00Z",
    "signal_dbm": -67.9,
    "noise_floor_dbm": -97.8,
    "link_quality": 0.96,
    "anomaly_detected": false
  },
  {
    "epoch": "2025-01-15T18:00:00Z",
    "signal_dbm": -68.7,
    "noise_floor_dbm": -97.5,
    "link_quality": 0.95,
    "anomaly_detected": false
  },
  {
    "epoch": "2025-01-15T19:00:00Z",
    "signal_dbm": -70.3,
    "noise_floor_dbm": -96.9,
    "link_quality": 0.90,
    "anomaly_detected": false
  }
]

const STARTER_CONFIG_HINT = {
  title: "Signal Monitor",
  subtitle: "Signal strength and link quality over time",
  left: {
    metrics: [{ key: "signal_dbm", label: "Signal (dBm)", color: "#3498db" }],
    fillUnder: true
  },
  right: {
    metrics: [{ key: "link_quality", label: "Link Quality (0–1)", color: "#27ae60" }]
  },
  flags: [{ key: "anomaly_detected", trueLabel: "Anomaly", trueColor: "#e74c3c", trueOnly: true, style: "line" }]
}

function buildSampleRecords(activeLeft, activeRight, activeFlags, count = 3) {
  const base = Date.now() - (count - 1) * 3600 * 1000
  return Array.from({ length: count }, (_, i) => {
    const rec = { epoch: new Date(base + i * 3600 * 1000).toISOString() }
    activeLeft.forEach(m  => { rec[m.key]  = parseFloat((Math.random() * 100).toFixed(3)) })
    activeRight.forEach(m => { rec[m.key]  = parseFloat((Math.random() * 1).toFixed(4)) })
    activeFlags.forEach(f => { rec[f.key]  = Math.random() > 0.7 })
    return rec
  })
}

function schemaComment(activeLeft, activeRight, activeFlags) {
  const fields = [
    { key: 'epoch', type: 'string', note: 'ISO 8601 timestamp or Unix epoch (seconds or ms)  required' },
    ...activeLeft.map(m  => ({ key: m.key,  type: 'number',  note: `left axis — ${m.label}` })),
    ...activeRight.map(m => ({ key: m.key,  type: 'number',  note: `right axis — ${m.label}` })),
    ...activeFlags.map(f => ({ key: f.key,  type: 'boolean', note: `flag — ${f.trueLabel}` })),
  ]
  return fields
}

export default function AdHocAnalytics() {
  const [chartId] = useState(() => uid())
  const [title, setTitle] = useState('')
  const [subtitle, setSubtitle] = useState('')
  const [leftMetrics, setLeftMetrics] = useState([emptyMetric(0)])
  const [rightMetrics, setRightMetrics] = useState([])
  const [flags, setFlags] = useState([])
  const [fillUnder, setFillUnder] = useState(false)
  const [useFixedRange, setUseFixedRange] = useState(false)
  const [fixedMin, setFixedMin] = useState('')
  const [fixedMax, setFixedMax] = useState('')
  const [bands, setBands] = useState([])

  const [dataRows, setDataRows] = useState([])
  const [newRow, setNewRow] = useState({})
  const [rowErrors, setRowErrors] = useState([])

  const [collectionUrl, setCollectionUrl] = useState('')
  const [collectionLoading, setCollectionLoading] = useState(false)
  const [collectionError, setCollectionError] = useState(null)
  const [collectionInfo, setCollectionInfo] = useState(null)
  const [showSchema, setShowSchema] = useState(false)

  const [previewing, setPreviewing] = useState(false)

  const fileInputRef = useRef(null)

  const activeLeft  = leftMetrics.filter(m => m.key.trim() && m.label.trim())
  const activeRight = rightMetrics.filter(m => m.key.trim() && m.label.trim())
  const activeFlags = flags.filter(f => f.key.trim() && f.trueLabel.trim())

  const configValid = !!(
    title.trim() &&
    leftMetrics.length > 0 &&
    leftMetrics.every(m => m.key.trim() && m.label.trim()) &&
    rightMetrics.every(m => m.key.trim() && m.label.trim()) &&
    flags.every(f => f.key.trim() && f.trueLabel.trim())
  )

  const hasActiveKeys = activeLeft.length > 0

  const chartConfig = useMemo(() => {
    if (!configValid) return null
    return {
      id: chartId,
      title,
      subtitle,
      hasData: (d) => activeLeft.some(m => d[m.key] != null),
      left: {
        metrics: activeLeft.map(({ key, label, color }) => ({ key, label, color })),
        fillUnder,
        ...(useFixedRange && fixedMin !== '' && fixedMax !== ''
          ? { fixedRange: { min: Number(fixedMin), max: Number(fixedMax) } }
          : {}),
      },
      right: { metrics: activeRight.map(({ key, label, color }) => ({ key, label, color })) },
      flags: activeFlags.map(({ key, trueColor, trueLabel, trueOnly, style }) =>
        ({ key, trueColor, trueLabel, trueOnly, style })),
      thresholdBands: bands
        .filter(b => b.min !== '' && b.max !== '')
        .map(({ min, max, color }) => ({ min: Number(min), max: Number(max), color })),
    }
  }, [configValid, chartId, title, subtitle, activeLeft, activeRight, activeFlags,
      fillUnder, useFixedRange, fixedMin, fixedMax, bands])

  const chartData = useMemo(() => {
    return dataRows
      .filter(r => isValidEpoch(r._epoch))
      .map(r => {
        const pt = { epoch: normalizeEpoch(r._epoch) }
        activeLeft.forEach(m => {
          const v = r[m.key]
          pt[m.key] = (v != null && v !== '') ? Number(v) : null
        })
        activeRight.forEach(m => {
          const v = r[m.key]
          pt[m.key] = (v != null && v !== '') ? Number(v) : null
        })
        activeFlags.forEach(f => {
          const v = r[f.key]
          pt[f.key] = (v == null || v === '') ? null : (v === 'true' || v === true)
        })
        return pt
      })
      .sort((a, b) => (a.epoch || '').localeCompare(b.epoch || ''))
  }, [dataRows, activeLeft, activeRight, activeFlags])

  const canPreview = configValid && chartData.length > 0

  function updateMetric(list, setList, id, field, val) {
    setList(list.map(m => m._id === id ? { ...m, [field]: val } : m))
  }
  function updateFlag(id, field, val) {
    setFlags(p => p.map(f => f._id === id ? { ...f, [field]: val } : f))
  }
  function updateBand(id, field, val) {
    setBands(p => p.map(b => b._id === id ? { ...b, [field]: val } : b))
  }

  function addRow() {
    const errs = []
    if (!isValidEpoch(newRow._epoch)) {
      errs.push('Epoch: enter a valid ISO date/time (e.g. 2025-01-01T12:00:00Z) or Unix timestamp in seconds.')
    }
    activeLeft.concat(activeRight).forEach(m => {
      const v = newRow[m.key]
      if (v != null && v !== '' && isNaN(Number(v)))
        errs.push(`"${m.label}" (${m.key}): must be a number.`)
    })
    activeFlags.forEach(f => {
      const v = newRow[f.key]
      if (v != null && v !== '' && v !== 'true' && v !== 'false')
        errs.push(`"${f.trueLabel}" (${f.key}): must be "true" or "false".`)
    })
    if (errs.length) { setRowErrors(errs); return }
    setRowErrors([])
    setDataRows(prev => [...prev, { ...newRow, _id: uid() }])
    setNewRow({})
  }

  function importCollection(arr, source) {
    if (!Array.isArray(arr) || arr.length === 0) {
      setCollectionError('Expected a non-empty JSON array.')
      return
    }
    const allKeys = [...activeLeft, ...activeRight].map(m => m.key)
    const flagKeys = activeFlags.map(f => f.key)
    let imported = 0, skipped = 0
    const rows = []
    arr.forEach(item => {
      const epochRaw = item.epoch ?? item.observation_epoch ?? item.timestamp ?? item.time
      if (!isValidEpoch(epochRaw)) { skipped++; return }
      const row = { _id: uid(), _epoch: String(epochRaw) }
      allKeys.forEach(k => {
        const v = item[k]
        row[k] = (v != null && v !== '') ? String(v) : ''
      })
      flagKeys.forEach(k => {
        const v = item[k]
        row[k] = v == null ? '' : String(Boolean(v))
      })
      rows.push(row)
      imported++
    })
    if (rows.length === 0) {
      setCollectionError(`No valid records found. All ${arr.length} items were missing a valid epoch field.`)
      return
    }
    setCollectionError(null)
    setDataRows(prev => {
      const existing = new Set(prev.map(r => r._epoch))
      const fresh = rows.filter(r => !existing.has(r._epoch))
      return [...prev, ...fresh]
    })
    setCollectionInfo(`Loaded ${imported} record${imported !== 1 ? 's' : ''} from ${source}${skipped ? ` (${skipped} skipped — missing epoch)` : ''}.`)
  }

  async function loadFromUrl() {
    if (!collectionUrl.trim()) return
    setCollectionLoading(true)
    setCollectionError(null)
    setCollectionInfo(null)
    try {
      const res = await apiFetch(collectionUrl.trim())
      if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`)
      const json = await res.json()
      const arr = Array.isArray(json) ? json : (json.data ?? json.results ?? json.records ?? json.items)
      if (!Array.isArray(arr)) throw new Error('Response is not a JSON array and has no recognised array key (data, results, records, items).')
      importCollection(arr, collectionUrl.trim())
    } catch (e) {
      setCollectionError(e.message)
    } finally {
      setCollectionLoading(false)
    }
  }

  function loadFromFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setCollectionError(null)
    setCollectionInfo(null)
    const reader = new FileReader()
    reader.onload = ev => {
      try {
        const json = JSON.parse(ev.target.result)
        const arr = Array.isArray(json) ? json : (json.data ?? json.results ?? json.records ?? json.items)
        if (!Array.isArray(arr)) throw new Error('File is not a JSON array and has no recognised array key (data, results, records, items).')
        importCollection(arr, file.name)
      } catch (err) {
        setCollectionError(err.message)
      }
      e.target.value = ''
    }
    reader.readAsText(file)
  }

  function downloadSample() {
    const sample = buildSampleRecords(activeLeft, activeRight, activeFlags, 3)
    const blob = new Blob([JSON.stringify(sample, null, 2)], { type: 'application/json' })
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(blob),
      download: `sample-collection-${title.trim().replace(/\s+/g, '-').toLowerCase() || 'adhoc'}.json`,
    })
    a.click()
    URL.revokeObjectURL(a.href)
  }

  function downloadStarterTemplate() {
    const blob = new Blob([JSON.stringify(STARTER_COLLECTION, null, 2)], { type: 'application/json' })
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(blob),
      download: 'starter-collection.json',
    })
    a.click()
    URL.revokeObjectURL(a.href)
  }

  function loadStarterTemplate() {
    importCollection(STARTER_COLLECTION, 'starter template')
  }

  function exportConfig() {
    if (!chartConfig) return
    const { hasData, ...exportable } = chartConfig
    const blob = new Blob([JSON.stringify(exportable, null, 2)], { type: 'application/json' })
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(blob),
      download: `analytic-${title.trim().replace(/\s+/g, '-').toLowerCase() || chartId}.json`,
    })
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const schemaFields = useMemo(
    () => schemaComment(activeLeft, activeRight, activeFlags),
    [activeLeft, activeRight, activeFlags]
  )

  const sampleJson = useMemo(
    () => buildSampleRecords(activeLeft, activeRight, activeFlags, 2),
    [activeLeft, activeRight, activeFlags]
  )

  return (
    <div className="adhoc-root">
      <div className="adhoc-header">
        <h2 className="adhoc-heading">Ad Hoc Analytics</h2>
        <p className="adhoc-desc">Build a custom analytic, link or upload a collection, and preview the chart. Export the config to add it to the dashboard.</p>
      </div>

      <div className="adhoc-body">

        {/* ── Step 1: Config ── */}
        <section className="adhoc-section">
          <div className="adhoc-section-head">
            <span className="adhoc-step-badge">1</span>
            <h3 className="adhoc-section-title">Configure Analytic</h3>
          </div>

          <div className="adhoc-field-group">
            <div className="adhoc-field-row">
              <label className="adhoc-label">Title <span className="adhoc-req">*</span></label>
              <input
                className="adhoc-input"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="e.g. Signal Strength"
              />
            </div>
            <div className="adhoc-field-row">
              <label className="adhoc-label">Subtitle</label>
              <input
                className="adhoc-input"
                value={subtitle}
                onChange={e => setSubtitle(e.target.value)}
                placeholder="e.g. dBm over time"
              />
            </div>
          </div>

          {/* Left axis */}
          <div className="adhoc-axis-block">
            <div className="adhoc-axis-head">
              <span className="adhoc-axis-name">Left Axis Metrics <span className="adhoc-req">*</span></span>
              <button className="adhoc-add-btn" onClick={() => setLeftMetrics(p => [...p, emptyMetric(p.length)])}>+ metric</button>
            </div>
            <div className="adhoc-metric-header"><span>Key</span><span>Label</span><span>Color</span></div>
            {leftMetrics.map(m => (
              <div key={m._id} className="adhoc-metric-row">
                <input className="adhoc-input adhoc-input--key" value={m.key}
                  onChange={e => updateMetric(leftMetrics, setLeftMetrics, m._id, 'key', e.target.value)} placeholder="myField" />
                <input className="adhoc-input adhoc-input--label" value={m.label}
                  onChange={e => updateMetric(leftMetrics, setLeftMetrics, m._id, 'label', e.target.value)} placeholder="My Field (unit)" />
                <input type="color" className="adhoc-color" value={m.color}
                  onChange={e => updateMetric(leftMetrics, setLeftMetrics, m._id, 'color', e.target.value)} />
                {leftMetrics.length > 1 && (
                  <button className="adhoc-rm-btn" onClick={() => setLeftMetrics(p => p.filter(x => x._id !== m._id))}>✕</button>
                )}
              </div>
            ))}
            <div className="adhoc-axis-opts">
              <label className="adhoc-check-label">
                <input type="checkbox" checked={fillUnder} onChange={e => setFillUnder(e.target.checked)} />
                Fill under metrics[0]
              </label>
              <label className="adhoc-check-label">
                <input type="checkbox" checked={useFixedRange} onChange={e => setUseFixedRange(e.target.checked)} />
                Fixed Y range
              </label>
              {useFixedRange && (
                <span className="adhoc-range-group">
                  <input className="adhoc-input adhoc-input--narrow" type="number" value={fixedMin}
                    onChange={e => setFixedMin(e.target.value)} placeholder="min" />
                  <span className="adhoc-range-sep">–</span>
                  <input className="adhoc-input adhoc-input--narrow" type="number" value={fixedMax}
                    onChange={e => setFixedMax(e.target.value)} placeholder="max" />
                </span>
              )}
            </div>
          </div>

          {/* Right axis */}
          <div className="adhoc-axis-block">
            <div className="adhoc-axis-head">
              <span className="adhoc-axis-name">Right Axis Metrics</span>
              <button className="adhoc-add-btn" onClick={() => setRightMetrics(p => [...p, emptyMetric(leftMetrics.length + p.length)])}>+ metric</button>
            </div>
            {rightMetrics.length === 0
              ? <p className="adhoc-empty-note">No right axis — it will be suppressed.</p>
              : <>
                  <div className="adhoc-metric-header"><span>Key</span><span>Label</span><span>Color</span></div>
                  {rightMetrics.map(m => (
                    <div key={m._id} className="adhoc-metric-row">
                      <input className="adhoc-input adhoc-input--key" value={m.key}
                        onChange={e => updateMetric(rightMetrics, setRightMetrics, m._id, 'key', e.target.value)} placeholder="myField" />
                      <input className="adhoc-input adhoc-input--label" value={m.label}
                        onChange={e => updateMetric(rightMetrics, setRightMetrics, m._id, 'label', e.target.value)} placeholder="My Field (unit)" />
                      <input type="color" className="adhoc-color" value={m.color}
                        onChange={e => updateMetric(rightMetrics, setRightMetrics, m._id, 'color', e.target.value)} />
                      <button className="adhoc-rm-btn" onClick={() => setRightMetrics(p => p.filter(x => x._id !== m._id))}>✕</button>
                    </div>
                  ))}
                </>
            }
          </div>

          {/* Flags */}
          <div className="adhoc-axis-block">
            <div className="adhoc-axis-head">
              <span className="adhoc-axis-name">Boolean Flags</span>
              <button className="adhoc-add-btn" onClick={() => setFlags(p => [...p, emptyFlag()])}>+ flag</button>
            </div>
            {flags.length === 0
              ? <p className="adhoc-empty-note">No flags configured.</p>
              : <>
                  <div className="adhoc-metric-header">
                    <span>Key</span><span>Label (true)</span><span>Color</span><span>Style</span><span>True only</span>
                  </div>
                  {flags.map(f => (
                    <div key={f._id} className="adhoc-metric-row">
                      <input className="adhoc-input adhoc-input--key" value={f.key}
                        onChange={e => updateFlag(f._id, 'key', e.target.value)} placeholder="myFlag" />
                      <input className="adhoc-input adhoc-input--label" value={f.trueLabel}
                        onChange={e => updateFlag(f._id, 'trueLabel', e.target.value)} placeholder="Anomaly detected" />
                      <input type="color" className="adhoc-color" value={f.trueColor}
                        onChange={e => updateFlag(f._id, 'trueColor', e.target.value)} />
                      <select className="adhoc-select" value={f.style}
                        onChange={e => updateFlag(f._id, 'style', e.target.value)}>
                        <option value="line">line</option>
                        <option value="dot">dot</option>
                      </select>
                      <input type="checkbox" checked={f.trueOnly}
                        onChange={e => updateFlag(f._id, 'trueOnly', e.target.checked)} />
                      <button className="adhoc-rm-btn" onClick={() => setFlags(p => p.filter(x => x._id !== f._id))}>✕</button>
                    </div>
                  ))}
                </>
            }
          </div>

          {/* Threshold bands */}
          <div className="adhoc-axis-block">
            <div className="adhoc-axis-head">
              <span className="adhoc-axis-name">Threshold Bands</span>
              <button className="adhoc-add-btn" onClick={() => setBands(p => [...p, emptyBand()])}>+ band</button>
            </div>
            {bands.length === 0
              ? <p className="adhoc-empty-note">No threshold bands configured.</p>
              : <>
                  <div className="adhoc-metric-header"><span>Min</span><span>Max</span><span>Color</span></div>
                  {bands.map(b => (
                    <div key={b._id} className="adhoc-metric-row">
                      <input className="adhoc-input adhoc-input--narrow" type="number" value={b.min}
                        onChange={e => updateBand(b._id, 'min', e.target.value)} placeholder="0" />
                      <input className="adhoc-input adhoc-input--narrow" type="number" value={b.max}
                        onChange={e => updateBand(b._id, 'max', e.target.value)} placeholder="100" />
                      <input type="color" className="adhoc-color"
                        value={b.color.length === 9 ? b.color.slice(0, 7) : b.color}
                        onChange={e => updateBand(b._id, 'color', e.target.value + '26')} />
                      <button className="adhoc-rm-btn" onClick={() => setBands(p => p.filter(x => x._id !== b._id))}>✕</button>
                    </div>
                  ))}
                </>
            }
          </div>
        </section>

        {/* ── Step 2: Link / Load Collection ── */}
        <section className="adhoc-section">
          <div className="adhoc-section-head">
            <span className="adhoc-step-badge">2</span>
            <h3 className="adhoc-section-title">Link a Collection</h3>
          </div>

          {/* Starter template — always visible */}
          <div className="adhoc-starter-block">
            <div className="adhoc-starter-head">
              <span className="adhoc-starter-title">Starter Template</span>
              <span className="adhoc-starter-badge">example</span>
            </div>
            <p className="adhoc-starter-desc">
              A 12-record signal-monitoring collection demonstrating all supported field types:
              a numeric left-axis metric (<code>signal_dbm</code>), a numeric right-axis metric (<code>link_quality</code>),
              and a boolean flag (<code>anomaly_detected</code>). To use it, configure the analytic with the matching
              keys below, then click <strong>Load into table</strong>.
            </p>
            <div className="adhoc-starter-config-hint">
              <span className="adhoc-starter-hint-label">Matching analytic config:</span>
              <pre className="adhoc-starter-pre">{JSON.stringify(STARTER_CONFIG_HINT, null, 2)}</pre>
            </div>
            <div className="adhoc-starter-actions">
              <button className="adhoc-starter-load-btn" onClick={loadStarterTemplate}>
                Load into table
              </button>
              <button className="adhoc-schema-dl" onClick={downloadStarterTemplate}>
                Download JSON
              </button>
            </div>
          </div>

          {!hasActiveKeys ? (
            <p className="adhoc-empty-note" style={{ marginTop: '0.5rem' }}>Configure at least one left axis metric first so the schema is known.</p>
          ) : (
            <>
              {/* Schema reference */}
              <div className="adhoc-schema-bar">
                <span className="adhoc-schema-label">Collection schema</span>
                <button className="adhoc-schema-toggle" onClick={() => setShowSchema(p => !p)}>
                  {showSchema ? 'Hide schema' : 'View schema'}
                </button>
                <button className="adhoc-schema-dl" onClick={downloadSample} title="Download a sample JSON file">
                  Download sample
                </button>
              </div>

              {showSchema && (
                <div className="adhoc-schema-block">
                  <div className="adhoc-schema-legend">
                    <span>A collection is a <strong>JSON array</strong> of flat objects. Each object must have an <code>epoch</code> field plus numeric and boolean fields matching the metric/flag keys configured above.</span>
                  </div>

                  <div className="adhoc-schema-fields">
                    <div className="adhoc-schema-field adhoc-schema-field--header">
                      <span>Field</span><span>Type</span><span>Note</span>
                    </div>
                    {schemaFields.map(f => (
                      <div key={f.key} className={`adhoc-schema-field ${f.key === 'epoch' ? 'adhoc-schema-field--epoch' : ''}`}>
                        <code>{f.key}</code>
                        <span className="adhoc-schema-type">{f.type}</span>
                        <span className="adhoc-schema-note">{f.note}</span>
                      </div>
                    ))}
                  </div>

                  <div className="adhoc-schema-sample-label">Sample (2 records):</div>
                  <pre className="adhoc-schema-pre">{JSON.stringify(sampleJson, null, 2)}</pre>

                  <div className="adhoc-schema-note-block">
                    <strong>Epoch field</strong> is detected from <code>epoch</code>, <code>observation_epoch</code>, <code>timestamp</code>, or <code>time</code> — whichever is present. Value may be an ISO 8601 string or a Unix timestamp in seconds or milliseconds.
                    <br />
                    <strong>Array envelope</strong> — the file or response may be a bare array <code>[ … ]</code> or an object with a top-level array key named <code>data</code>, <code>results</code>, <code>records</code>, or <code>items</code>.
                    <br />
                    <strong>Extra fields</strong> in a record are silently ignored.
                  </div>
                </div>
              )}

              {/* Load from URL */}
              <div className="adhoc-load-block">
                <div className="adhoc-load-title">Load from URL</div>
                <div className="adhoc-load-row">
                  <input
                    className="adhoc-input adhoc-url-input"
                    type="url"
                    value={collectionUrl}
                    onChange={e => setCollectionUrl(e.target.value)}
                    placeholder="https://… or /api/observations/25544"
                    onKeyDown={e => e.key === 'Enter' && loadFromUrl()}
                  />
                  <button
                    className="adhoc-load-btn"
                    disabled={!collectionUrl.trim() || collectionLoading}
                    onClick={loadFromUrl}
                  >
                    {collectionLoading ? 'Loading…' : 'Fetch'}
                  </button>
                </div>
                <p className="adhoc-load-hint">
                  Same-origin requests include your session token automatically. The endpoint must return JSON matching the schema above.
                </p>
              </div>

              {/* Upload file */}
              <div className="adhoc-load-block">
                <div className="adhoc-load-title">Upload JSON file</div>
                <div className="adhoc-load-row">
                  <button className="adhoc-file-btn" onClick={() => fileInputRef.current?.click()}>
                    Choose file…
                  </button>
                  <input ref={fileInputRef} type="file" accept=".json,application/json" style={{ display: 'none' }} onChange={loadFromFile} />
                  <span className="adhoc-load-hint" style={{ marginTop: 0 }}>
                    Select a <code>.json</code> file matching the schema above. Records are merged with any existing data.
                  </span>
                </div>
              </div>

              {collectionError && (
                <div className="adhoc-errors" style={{ marginTop: '0.5rem' }}>
                  <div className="adhoc-error-item">{collectionError}</div>
                </div>
              )}
              {collectionInfo && (
                <div className="adhoc-collection-info">{collectionInfo}</div>
              )}
            </>
          )}
        </section>

        {/* ── Step 3: Manual Data Entry ── */}
        <section className="adhoc-section">
          <div className="adhoc-section-head">
            <span className="adhoc-step-badge">3</span>
            <h3 className="adhoc-section-title">Data Points</h3>
            {dataRows.length > 0 && (
              <button className="adhoc-clear-btn" onClick={() => { setDataRows([]); setCollectionInfo(null) }}>
                Clear all
              </button>
            )}
          </div>

          {!hasActiveKeys ? (
            <p className="adhoc-empty-note">Configure at least one left axis metric with a key and label first.</p>
          ) : (
            <>
              <div className="adhoc-table-wrap">
                <table className="adhoc-table">
                  <thead>
                    <tr>
                      <th>Epoch <span className="adhoc-th-hint">ISO or Unix ts</span></th>
                      {activeLeft.map(m => (
                        <th key={m._id} style={{ color: m.color }}>{m.key} <span className="adhoc-th-hint">number</span></th>
                      ))}
                      {activeRight.map(m => (
                        <th key={m._id} style={{ color: m.color }}>{m.key} <span className="adhoc-th-hint">number</span></th>
                      ))}
                      {activeFlags.map(f => (
                        <th key={f._id} style={{ color: f.trueColor }}>{f.key} <span className="adhoc-th-hint">bool</span></th>
                      ))}
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataRows.map(r => (
                      <tr key={r._id}>
                        <td className="adhoc-td-epoch">{r._epoch}</td>
                        {activeLeft.map(m => <td key={m._id}>{r[m.key] ?? ''}</td>)}
                        {activeRight.map(m => <td key={m._id}>{r[m.key] ?? ''}</td>)}
                        {activeFlags.map(f => (
                          <td key={f._id} className={r[f.key] === 'true' ? 'adhoc-td-true' : r[f.key] === 'false' ? 'adhoc-td-false' : ''}>
                            {r[f.key] ?? ''}
                          </td>
                        ))}
                        <td>
                          <button className="adhoc-rm-btn" onClick={() => setDataRows(p => p.filter(x => x._id !== r._id))}>✕</button>
                        </td>
                      </tr>
                    ))}

                    {/* Manual input row */}
                    <tr className="adhoc-input-row">
                      <td>
                        <input
                          className="adhoc-input adhoc-input--cell"
                          value={newRow._epoch || ''}
                          onChange={e => setNewRow(p => ({ ...p, _epoch: e.target.value }))}
                          placeholder="2025-01-01T00:00:00Z"
                          onKeyDown={e => e.key === 'Enter' && addRow()}
                        />
                      </td>
                      {activeLeft.map(m => (
                        <td key={m._id}>
                          <input className="adhoc-input adhoc-input--cell" type="number"
                            value={newRow[m.key] ?? ''} placeholder="0"
                            onChange={e => setNewRow(p => ({ ...p, [m.key]: e.target.value }))}
                            onKeyDown={e => e.key === 'Enter' && addRow()} />
                        </td>
                      ))}
                      {activeRight.map(m => (
                        <td key={m._id}>
                          <input className="adhoc-input adhoc-input--cell" type="number"
                            value={newRow[m.key] ?? ''} placeholder="0"
                            onChange={e => setNewRow(p => ({ ...p, [m.key]: e.target.value }))}
                            onKeyDown={e => e.key === 'Enter' && addRow()} />
                        </td>
                      ))}
                      {activeFlags.map(f => (
                        <td key={f._id}>
                          <select className="adhoc-select adhoc-select--cell"
                            value={newRow[f.key] ?? ''}
                            onChange={e => setNewRow(p => ({ ...p, [f.key]: e.target.value }))}>
                            <option value="">—</option>
                            <option value="true">true</option>
                            <option value="false">false</option>
                          </select>
                        </td>
                      ))}
                      <td>
                        <button className="adhoc-add-row-btn" onClick={addRow}>Add</button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {rowErrors.length > 0 && (
                <div className="adhoc-errors">
                  {rowErrors.map((e, i) => <div key={i} className="adhoc-error-item">{e}</div>)}
                </div>
              )}
              <p className="adhoc-row-count">{dataRows.length} data point{dataRows.length !== 1 ? 's' : ''}</p>
            </>
          )}
        </section>

        {/* ── Step 4: Preview & Export ── */}
        <section className="adhoc-section">
          <div className="adhoc-section-head">
            <span className="adhoc-step-badge">4</span>
            <h3 className="adhoc-section-title">Preview & Export</h3>
          </div>

          <div className="adhoc-actions">
            <button className="adhoc-preview-btn" disabled={!canPreview} onClick={() => setPreviewing(p => !p)}>
              {previewing ? 'Hide Preview' : 'Preview Chart'}
            </button>
            <button className="adhoc-export-btn" disabled={!configValid} onClick={exportConfig}>
              Export Config JSON
            </button>
          </div>

          {!canPreview && (
            <p className="adhoc-empty-note">
              {!configValid
                ? 'Complete the analytic configuration above.'
                : 'Add at least one valid data point to enable preview.'}
            </p>
          )}

          {previewing && canPreview && chartConfig && (
            <div className="adhoc-preview-wrap">
              <TimeSeriesChart {...chartConfig} data={chartData} />
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

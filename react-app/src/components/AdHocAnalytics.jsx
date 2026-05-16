import { useState, useMemo } from 'react'
import { TimeSeriesChart } from './ObservationDashboard'
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

  const [previewing, setPreviewing] = useState(false)

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

  return (
    <div className="adhoc-root">
      <div className="adhoc-header">
        <h2 className="adhoc-heading">Ad Hoc Analytics</h2>
        <p className="adhoc-desc">Build a custom analytic, populate it with data, and preview the chart. Export the config to add it to the dashboard.</p>
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
              <button
                className="adhoc-add-btn"
                onClick={() => setLeftMetrics(p => [...p, emptyMetric(p.length)])}
              >+ metric</button>
            </div>
            <div className="adhoc-metric-header">
              <span>Key</span><span>Label</span><span>Color</span>
            </div>
            {leftMetrics.map(m => (
              <div key={m._id} className="adhoc-metric-row">
                <input
                  className="adhoc-input adhoc-input--key"
                  value={m.key}
                  onChange={e => updateMetric(leftMetrics, setLeftMetrics, m._id, 'key', e.target.value)}
                  placeholder="myField"
                />
                <input
                  className="adhoc-input adhoc-input--label"
                  value={m.label}
                  onChange={e => updateMetric(leftMetrics, setLeftMetrics, m._id, 'label', e.target.value)}
                  placeholder="My Field (unit)"
                />
                <input
                  type="color"
                  className="adhoc-color"
                  value={m.color}
                  onChange={e => updateMetric(leftMetrics, setLeftMetrics, m._id, 'color', e.target.value)}
                />
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
                  <input
                    className="adhoc-input adhoc-input--narrow"
                    type="number"
                    value={fixedMin}
                    onChange={e => setFixedMin(e.target.value)}
                    placeholder="min"
                  />
                  <span className="adhoc-range-sep">–</span>
                  <input
                    className="adhoc-input adhoc-input--narrow"
                    type="number"
                    value={fixedMax}
                    onChange={e => setFixedMax(e.target.value)}
                    placeholder="max"
                  />
                </span>
              )}
            </div>
          </div>

          {/* Right axis */}
          <div className="adhoc-axis-block">
            <div className="adhoc-axis-head">
              <span className="adhoc-axis-name">Right Axis Metrics</span>
              <button
                className="adhoc-add-btn"
                onClick={() => setRightMetrics(p => [...p, emptyMetric(leftMetrics.length + p.length)])}
              >+ metric</button>
            </div>
            {rightMetrics.length === 0
              ? <p className="adhoc-empty-note">No right axis — it will be suppressed.</p>
              : (
                <>
                  <div className="adhoc-metric-header"><span>Key</span><span>Label</span><span>Color</span></div>
                  {rightMetrics.map(m => (
                    <div key={m._id} className="adhoc-metric-row">
                      <input
                        className="adhoc-input adhoc-input--key"
                        value={m.key}
                        onChange={e => updateMetric(rightMetrics, setRightMetrics, m._id, 'key', e.target.value)}
                        placeholder="myField"
                      />
                      <input
                        className="adhoc-input adhoc-input--label"
                        value={m.label}
                        onChange={e => updateMetric(rightMetrics, setRightMetrics, m._id, 'label', e.target.value)}
                        placeholder="My Field (unit)"
                      />
                      <input
                        type="color"
                        className="adhoc-color"
                        value={m.color}
                        onChange={e => updateMetric(rightMetrics, setRightMetrics, m._id, 'color', e.target.value)}
                      />
                      <button className="adhoc-rm-btn" onClick={() => setRightMetrics(p => p.filter(x => x._id !== m._id))}>✕</button>
                    </div>
                  ))}
                </>
              )
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
              : (
                <>
                  <div className="adhoc-metric-header">
                    <span>Key</span><span>Label (true)</span><span>Color</span><span>Style</span><span>True only</span>
                  </div>
                  {flags.map(f => (
                    <div key={f._id} className="adhoc-metric-row">
                      <input
                        className="adhoc-input adhoc-input--key"
                        value={f.key}
                        onChange={e => updateFlag(f._id, 'key', e.target.value)}
                        placeholder="myFlag"
                      />
                      <input
                        className="adhoc-input adhoc-input--label"
                        value={f.trueLabel}
                        onChange={e => updateFlag(f._id, 'trueLabel', e.target.value)}
                        placeholder="Anomaly detected"
                      />
                      <input
                        type="color"
                        className="adhoc-color"
                        value={f.trueColor}
                        onChange={e => updateFlag(f._id, 'trueColor', e.target.value)}
                      />
                      <select
                        className="adhoc-select"
                        value={f.style}
                        onChange={e => updateFlag(f._id, 'style', e.target.value)}
                      >
                        <option value="line">line</option>
                        <option value="dot">dot</option>
                      </select>
                      <input
                        type="checkbox"
                        checked={f.trueOnly}
                        onChange={e => updateFlag(f._id, 'trueOnly', e.target.checked)}
                      />
                      <button className="adhoc-rm-btn" onClick={() => setFlags(p => p.filter(x => x._id !== f._id))}>✕</button>
                    </div>
                  ))}
                </>
              )
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
              : (
                <>
                  <div className="adhoc-metric-header"><span>Min</span><span>Max</span><span>Color</span></div>
                  {bands.map(b => (
                    <div key={b._id} className="adhoc-metric-row">
                      <input
                        className="adhoc-input adhoc-input--narrow"
                        type="number"
                        value={b.min}
                        onChange={e => updateBand(b._id, 'min', e.target.value)}
                        placeholder="0"
                      />
                      <input
                        className="adhoc-input adhoc-input--narrow"
                        type="number"
                        value={b.max}
                        onChange={e => updateBand(b._id, 'max', e.target.value)}
                        placeholder="100"
                      />
                      <input
                        type="color"
                        className="adhoc-color"
                        value={b.color.length === 9 ? b.color.slice(0, 7) : b.color}
                        onChange={e => updateBand(b._id, 'color', e.target.value + '26')}
                      />
                      <button className="adhoc-rm-btn" onClick={() => setBands(p => p.filter(x => x._id !== b._id))}>✕</button>
                    </div>
                  ))}
                </>
              )
            }
          </div>
        </section>

        {/* ── Step 2: Data ── */}
        <section className="adhoc-section">
          <div className="adhoc-section-head">
            <span className="adhoc-step-badge">2</span>
            <h3 className="adhoc-section-title">Enter Data Points</h3>
          </div>

          {activeLeft.length === 0 ? (
            <p className="adhoc-empty-note">Configure at least one left axis metric with a key and label first.</p>
          ) : (
            <>
              <div className="adhoc-table-wrap">
                <table className="adhoc-table">
                  <thead>
                    <tr>
                      <th>
                        Epoch
                        <span className="adhoc-th-hint"> ISO or Unix ts</span>
                      </th>
                      {activeLeft.map(m => (
                        <th key={m._id} style={{ color: m.color }}>
                          {m.key}
                          <span className="adhoc-th-hint"> number</span>
                        </th>
                      ))}
                      {activeRight.map(m => (
                        <th key={m._id} style={{ color: m.color }}>
                          {m.key}
                          <span className="adhoc-th-hint"> number</span>
                        </th>
                      ))}
                      {activeFlags.map(f => (
                        <th key={f._id} style={{ color: f.trueColor }}>
                          {f.key}
                          <span className="adhoc-th-hint"> bool</span>
                        </th>
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

                    {/* Input row */}
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
                          <input
                            className="adhoc-input adhoc-input--cell"
                            type="number"
                            value={newRow[m.key] ?? ''}
                            onChange={e => setNewRow(p => ({ ...p, [m.key]: e.target.value }))}
                            placeholder="0"
                            onKeyDown={e => e.key === 'Enter' && addRow()}
                          />
                        </td>
                      ))}
                      {activeRight.map(m => (
                        <td key={m._id}>
                          <input
                            className="adhoc-input adhoc-input--cell"
                            type="number"
                            value={newRow[m.key] ?? ''}
                            onChange={e => setNewRow(p => ({ ...p, [m.key]: e.target.value }))}
                            placeholder="0"
                            onKeyDown={e => e.key === 'Enter' && addRow()}
                          />
                        </td>
                      ))}
                      {activeFlags.map(f => (
                        <td key={f._id}>
                          <select
                            className="adhoc-select adhoc-select--cell"
                            value={newRow[f.key] ?? ''}
                            onChange={e => setNewRow(p => ({ ...p, [f.key]: e.target.value }))}
                          >
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

        {/* ── Step 3: Preview & Export ── */}
        <section className="adhoc-section">
          <div className="adhoc-section-head">
            <span className="adhoc-step-badge">3</span>
            <h3 className="adhoc-section-title">Preview & Export</h3>
          </div>

          <div className="adhoc-actions">
            <button
              className="adhoc-preview-btn"
              disabled={!canPreview}
              onClick={() => setPreviewing(p => !p)}
            >
              {previewing ? 'Hide Preview' : 'Preview Chart'}
            </button>
            <button
              className="adhoc-export-btn"
              disabled={!configValid}
              onClick={exportConfig}
            >
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

import { useState, useEffect, useMemo, useRef } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import { buildChartData } from '../utils/observationTransforms'
import './ObservationDashboard.css'

const SVG_W = 820
const SVG_H = 170
const P = { top: 24, right: 88, bottom: 44, left: 72 }
const IW = SVG_W - P.left - P.right
const IH = SVG_H - P.top - P.bottom

const COLORS = {
  health:       '#27ae60',
  healthLow:    '#e74c3c',
  roll:         '#9b59b6',
  pitch:        '#3498db',
  yaw:          '#1abc9c',
  temp:         '#e67e22',
  tempVariance: '#e74c3c',
  reflectivity: '#16a085',
  confidence:   '#8e44ad',
  range:        '#2980b9',
  velocity:     '#f39c12',
  deltaV:       '#6c3483',
  manConf:      '#7f8c8d',
  drift:        '#e67e22',
  perigee:      '#1a252f',
  spin:         '#2c3e50',
  mass:         '#7f8c8d',
}

function niceRange(vals) {
  const valid = vals.filter(v => v != null && isFinite(v))
  if (!valid.length) return { min: 0, max: 1 }
  let mn = Math.min(...valid)
  let mx = Math.max(...valid)
  if (mn === mx) {
    const pad = Math.abs(mn) * 0.1 || 1
    mn -= pad; mx += pad
  } else {
    const pad = (mx - mn) * 0.05
    mn -= pad; mx += pad
  }
  return { min: mn, max: mx }
}

function niceTicks(min, max, count = 5) {
  const step = (max - min) / (count - 1)
  return Array.from({ length: count }, (_, i) => min + step * i)
}

function xPx(i, n) {
  if (n <= 1) return P.left + IW / 2
  return P.left + (i / (n - 1)) * IW
}

function yPx(val, min, max) {
  if (max === min) return P.top + IH / 2
  return P.top + IH - ((val - min) / (max - min)) * IH
}

function buildLinePath(data, keyFn, xFn, yFn) {
  let path = ''
  let started = false
  data.forEach((d, i) => {
    const v = keyFn(d)
    if (v == null || !isFinite(v)) { started = false; return }
    const x = xFn(i, data.length).toFixed(1)
    const y = yFn(v).toFixed(1)
    path += started ? ` L${x},${y}` : `M${x},${y}`
    started = true
  })
  return path
}

function formatLabel(v) {
  if (v == null) return ''
  if (Math.abs(v) >= 10000) return `${(v / 1000).toFixed(1)}k`
  if (Math.abs(v) >= 1000) return v.toFixed(0)
  if (Math.abs(v) >= 100) return v.toFixed(1)
  if (Math.abs(v) >= 10) return v.toFixed(2)
  return v.toFixed(3)
}

function formatEpoch(epoch) {
  if (!epoch) return ''
  return epoch.substring(5, 10)
}

function formatEpochFull(epoch) {
  if (!epoch) return ''
  return epoch.substring(0, 16).replace('T', ' ')
}

// DRAW ORDER: metrics render in array order — first under, last on top.
// Last item wins at overlaps. Reorder for data reasons only, not aesthetics.
// SCALE NOTE: all metrics on the same axis share one auto-computed scale.
// If magnitudes differ wildly, override with: left: { metrics: [...], fixedRange: { min, max } }
// CARD ORDER: array order determines card order in the dashboard grid.
//   Reordering entries here reorders cards. Do not rearrange JSX to move cards.
// hasData CONVENTION: test whether the primary left metric has any data.
//   A chart with only tbd or right-side metrics and no left data renders a blank card.
const ANALYTICS_CONFIG = [
  {
    id: 'health',
    title: 'Health Score',
    subtitle: 'Derived health score over time (0–100)',
    hasData: (d) => d.health != null,
    left: {
      metrics: [{ key: 'health', label: 'Health Score', color: COLORS.health }],
      fillUnder: true,
      fixedRange: { min: 0, max: 100 },
    },
    right: { metrics: [] },
    thresholdBands: [
      { min: 80, max: 100, color: 'rgba(39,174,96,0.06)' },
      { min: 60, max: 80,  color: 'rgba(243,156,18,0.06)' },
      { min: 40, max: 60,  color: 'rgba(230,126,34,0.06)' },
      { min: 0,  max: 40,  color: 'rgba(231,76,60,0.06)' },
    ],
  },
  {
    id: 'attitude',
    title: 'Attitude',
    subtitle: 'Roll, Pitch, Yaw over time',
    hasData: (d) => d.roll != null || d.pitch != null || d.yaw != null,
    left: {
      metrics: [
        { key: 'roll',  label: 'Roll (°)',  color: COLORS.roll },
        { key: 'pitch', label: 'Pitch (°)', color: COLORS.pitch },
        { key: 'yaw',   label: 'Yaw (°)',   color: COLORS.yaw },
      ],
      fillUnder: false,
    },
    right: { metrics: [] },
    flags: [
      { key: 'isUnstable', trueColor: '#e74c3c', trueLabel: 'Unstable', trueOnly: true, style: 'line' },
    ],
  },
  {
    id: 'thermal',
    title: 'Thermal',
    subtitle: 'Surface temperature and variance',
    hasData: (d) => d.temp != null,
    left: {
      metrics: [{ key: 'temp', label: 'Surface Temp (K)', color: COLORS.temp }],
      fillUnder: true,
    },
    right: {
      metrics: [{ key: 'tempVariance', label: 'Variance 30d', color: COLORS.tempVariance }],
    },
    flags: [
      { key: 'thermalAnomaly', trueColor: '#e74c3c', trueLabel: 'Anomaly', trueOnly: true, style: 'line' },
    ],
  },
  {
    id: 'material',
    title: 'Material Signature',
    subtitle: 'Reflectivity index and confidence',
    hasData: (d) => d.reflectivity != null,
    left: {
      metrics: [{ key: 'reflectivity', label: 'Reflectivity Index', color: COLORS.reflectivity }],
    },
    right: {
      metrics: [{ key: 'materialConfidence', label: 'Confidence', color: COLORS.confidence }],
    },
  },
  {
    id: 'proximity',
    title: 'Proximity State',
    subtitle: 'Range and relative velocity',
    hasData: (d) => d.range != null,
    left: {
      metrics: [{ key: 'range', label: 'Range (km)', color: COLORS.range }],
    },
    right: {
      metrics: [{ key: 'velocity', label: 'Rel. Velocity (m/s)', color: COLORS.velocity }],
    },
  },
  {
    id: 'maneuver',
    title: 'Maneuver Indicator',
    subtitle: 'ΔV residual and confidence',
    hasData: (d) => d.deltaV != null,
    left: {
      metrics: [{ key: 'deltaV', label: 'ΔV Residual (m/s)', color: COLORS.deltaV }],
    },
    right: {
      metrics: [{ key: 'manConf', label: 'Confidence', color: COLORS.manConf }],
    },
    flags: [
      { key: 'manFlag', trueColor: '#ff6b6b', trueLabel: 'Maneuver detected', trueOnly: true, style: 'line' },
    ],
  },
  {
    id: 'orbital-decay',
    title: 'Orbital Decay',
    subtitle: 'Perigee drift rate and estimated perigee altitude',
    hasData: (d) => d.drift != null || d.estimatedPerigee != null,
    left: {
      metrics: [{ key: 'drift', label: 'Perigee Drift (km/d)', color: COLORS.drift }],
    },
    right: {
      metrics: [{ key: 'estimatedPerigee', label: 'Est. Perigee (km)', color: COLORS.perigee }],
    },
  },
  {
    id: 'physical',
    title: 'Physical Properties',
    subtitle: 'Estimated mass and spin rate',
    hasData: (d) => d.mass != null || d.spin != null,
    left: {
      metrics: [{ key: 'mass', label: 'Mass (kg)', color: COLORS.mass }],
    },
    right: {
      metrics: [{ key: 'spin', label: 'Spin Rate (rpm)', color: COLORS.spin }],
    },
  },
]

function TimeSeriesChart({
  title, subtitle, data, id,
  left,           // { metrics: [{key, label, color, tbd?, format?}], fillUnder?: bool, fixedRange?: {min, max} }
  right,          // { metrics: [{key, label, color, tbd?, format?}] } | null/undefined
  flags,          // [{key, trueColor, trueLabel, trueOnly?, style?, tbd?}] | undefined
  thresholdBands, // [{min, max, color}] | undefined
  height = SVG_H,
}) {
  const [hovered, setHovered] = useState(null)
  const n = data.length

  const leftMetrics  = left.metrics || []
  const rightMetrics = right?.metrics || []

  const activeLeftMetrics  = leftMetrics.filter(m => !m.tbd)
  const activeRightMetrics = rightMetrics.filter(m => !m.tbd)
  const hasRightAxis = activeRightMetrics.length > 0

  const lVals = activeLeftMetrics.flatMap(m => data.map(d => d[m.key]))
  const lRange = left.fixedRange || niceRange(lVals)

  const rVals = hasRightAxis ? activeRightMetrics.flatMap(m => data.map(d => d[m.key])) : []
  const rRange = hasRightAxis ? niceRange(rVals) : null

  const lTicks = niceTicks(lRange.min, lRange.max)
  const rTicks = rRange ? niceTicks(rRange.min, rRange.max) : []

  const innerH = height - P.top - P.bottom
  function yL(v) { return P.top + innerH - ((v - lRange.min) / (lRange.max - lRange.min)) * innerH }
  function yR(v) { return P.top + innerH - ((v - rRange.min) / (rRange.max - rRange.min)) * innerH }

  const gradId = `grad-${id}`
  const primaryLeft = activeLeftMetrics[0]
  const hasLeftData = primaryLeft != null && data.some(d => d[primaryLeft.key] != null && isFinite(d[primaryLeft.key]))

  const labelStep = n > 20 ? Math.ceil(n / 12) : n > 10 ? 2 : 1
  const hovD = hovered != null ? data[hovered] : null
  const activeFlags = (flags || []).filter(f => !f.tbd)

  return (
    <div className="obs-chart-card">
      <div className="obs-chart-header">
        <h3>{title}</h3>
        {subtitle && <span className="obs-chart-subtitle">{subtitle}</span>}
      </div>
      <div className="obs-chart-legend">
        {leftMetrics.map(m => (
          <span key={m.key} className="obs-legend-item" style={{ color: m.tbd ? '#bdc3c7' : m.color }}>
            <span className="obs-legend-dot" style={{ background: m.tbd ? '#bdc3c7' : m.color }} />
            {m.label}{m.tbd ? ' (tbd)' : ''}
          </span>
        ))}
        {rightMetrics.map(m => (
          <span key={m.key} className="obs-legend-item obs-legend-right" style={{ color: m.tbd ? '#bdc3c7' : m.color }}>
            <span className="obs-legend-dot obs-legend-dot-dashed" style={{ background: m.tbd ? '#bdc3c7' : m.color }} />
            {m.label}{m.tbd ? ' (tbd)' : ' (→)'}
          </span>
        ))}
      </div>

      <svg
        viewBox={`0 0 ${SVG_W} ${height}`}
        className="obs-svg"
        onMouseLeave={() => setHovered(null)}
      >
        <defs>
          {primaryLeft && (
            <linearGradient id={gradId} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={primaryLeft.color} stopOpacity="0.25" />
              <stop offset="100%" stopColor={primaryLeft.color} stopOpacity="0.02" />
            </linearGradient>
          )}
          <clipPath id={`clip-${id}`}>
            <rect x={P.left} y={P.top} width={IW} height={innerH} />
          </clipPath>
        </defs>

        {/* Threshold bands */}
        {(thresholdBands || []).map((band, bi) => (
          <rect
            key={bi}
            x={P.left} y={yL(band.max)}
            width={IW} height={yL(band.min) - yL(band.max)}
            fill={band.color}
            clipPath={`url(#clip-${id})`}
          />
        ))}

        {/* Grid lines */}
        {lTicks.map((t, ti) => (
          <line
            key={ti}
            x1={P.left} y1={yL(t).toFixed(1)}
            x2={P.left + IW} y2={yL(t).toFixed(1)}
            stroke="#eef0f3" strokeWidth="1"
          />
        ))}

        {/* Left Y axis labels */}
        {lTicks.map((t, ti) => (
          <text
            key={ti}
            x={P.left - 8} y={yL(t) + 4}
            textAnchor="end" fontSize="11" fill={primaryLeft?.color || '#888'}
          >
            {formatLabel(t)}
          </text>
        ))}

        {/* Left axis label */}
        {primaryLeft && (
          <text
            x={20} y={P.top + innerH / 2}
            textAnchor="middle" fontSize="12" fontWeight="600"
            fill={primaryLeft.color}
            transform={`rotate(-90, 20, ${P.top + innerH / 2})`}
          >
            {primaryLeft.label}
          </text>
        )}

        {/* Right Y axis */}
        {hasRightAxis && <>
          {rTicks.map((t, ti) => (
            <text
              key={ti}
              x={P.left + IW + 8} y={yR(t) + 4}
              textAnchor="start" fontSize="11" fill={activeRightMetrics[0].color}
            >
              {formatLabel(t)}
            </text>
          ))}
          <line
            x1={P.left + IW} y1={P.top}
            x2={P.left + IW} y2={P.top + innerH}
            stroke="#dee2e6" strokeWidth="1"
          />
          <text
            x={SVG_W - 14} y={P.top + innerH / 2}
            textAnchor="middle" fontSize="12" fontWeight="600"
            fill={activeRightMetrics[0].color}
            transform={`rotate(90, ${SVG_W - 14}, ${P.top + innerH / 2})`}
          >
            {activeRightMetrics[0].label}
          </text>
        </>}

        {/* X axis labels */}
        {data.map((d, i) => {
          if (i % labelStep !== 0 && i !== n - 1) return null
          return (
            <text
              key={i}
              x={xPx(i, n).toFixed(1)} y={P.top + innerH + 18}
              textAnchor="middle" fontSize="10" fill="#888"
            >
              {formatEpoch(d.epoch)}
            </text>
          )
        })}

        {/* Flag dots at bottom (dot mode only) */}
        {activeFlags.filter(f => f.style !== 'line').map((flag, fi) =>
          data.map((d, i) => {
            const v = d[flag.key]
            if (v == null) return null
            if (flag.trueOnly && v !== true) return null
            const col = v ? flag.trueColor : (flag.falseColor || '#2ecc71')
            return (
              <circle
                key={`${fi}-${i}`}
                cx={xPx(i, n)} cy={P.top + innerH + 32}
                r={4} fill={col} opacity={0.9}
              />
            )
          })
        )}

        {/* Axes */}
        <line x1={P.left} y1={P.top} x2={P.left} y2={P.top + innerH} stroke="#bdc3c7" strokeWidth="1.5" />
        <line x1={P.left} y1={P.top + innerH} x2={P.left + IW} y2={P.top + innerH} stroke="#bdc3c7" strokeWidth="1.5" />

        <g clipPath={`url(#clip-${id})`}>
          {/* Flag vertical lines (line mode) — rendered first so they appear behind data */}
          {activeFlags.filter(f => f.style === 'line').map((flag, fi) =>
            data.map((d, i) => {
              const v = d[flag.key]
              if (v == null) return null
              if (flag.trueOnly && v !== true) return null
              const col = v ? flag.trueColor : (flag.falseColor || '#2ecc71')
              const offset = fi * 1.5
              return (
                <line
                  key={`fl-${fi}-${i}`}
                  x1={(xPx(i, n) + offset).toFixed(1)} y1={P.top}
                  x2={(xPx(i, n) + offset).toFixed(1)} y2={P.top + innerH}
                  stroke={col} strokeWidth="2" opacity="0.5"
                />
              )
            })
          )}

          {/* Area fill under primary left metric */}
          {left.fillUnder && hasLeftData && (() => {
            const linePts = data
              .map((d, i) => {
                const v = d[primaryLeft.key]
                if (v == null || !isFinite(v)) return null
                return { x: xPx(i, n), y: yL(v) }
              })
              .filter(Boolean)
            if (!linePts.length) return null
            const linePath2 = linePts.map((p, pi) => `${pi === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
            const areaPath = `${linePath2} L${linePts[linePts.length - 1].x.toFixed(1)},${P.top + innerH} L${linePts[0].x.toFixed(1)},${P.top + innerH} Z`
            return <path d={areaPath} fill={`url(#${gradId})`} />
          })()}

          {/* Left metrics lines */}
          {activeLeftMetrics.map((m, mi) => {
            const path = buildLinePath(data, d => d[m.key], xPx, yL)
            return (
              <path
                key={mi}
                d={path}
                fill="none"
                stroke={m.color}
                strokeWidth={mi === 0 ? 2.2 : 2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            )
          })}

          {/* Right metrics lines (dashed) */}
          {activeRightMetrics.map((m, mi) => {
            const path = buildLinePath(data, d => d[m.key], xPx, yR)
            return (
              <path
                key={mi}
                d={path}
                fill="none"
                stroke={m.color}
                strokeWidth="2"
                strokeDasharray="5,3"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            )
          })}

          {/* Hover interaction overlay */}
          {data.map((d, i) => (
            <rect
              key={i}
              x={xPx(i, n) - (n > 1 ? IW / n / 2 : IW / 2)}
              y={P.top} width={n > 1 ? IW / n : IW} height={innerH}
              fill="transparent"
              onMouseEnter={() => setHovered(i)}
            />
          ))}

          {/* Hover dot + vertical line */}
          {hovered != null && (() => {
            const d = data[hovered]
            const x = xPx(hovered, n)
            return (
              <g>
                <line x1={x} y1={P.top} x2={x} y2={P.top + innerH} stroke="#bdc3c7" strokeWidth="1" strokeDasharray="4,2" />
                {activeLeftMetrics.map((m, mi) => {
                  const v = d[m.key]
                  if (v == null || !isFinite(v)) return null
                  return <circle key={mi} cx={x} cy={yL(v)} r={mi === 0 ? 5 : 4} fill={m.color} stroke="white" strokeWidth="2" />
                })}
                {activeRightMetrics.map((m, mi) => {
                  const v = d[m.key]
                  if (v == null || !isFinite(v)) return null
                  return <circle key={mi} cx={x} cy={yR(v)} r={mi === 0 ? 5 : 4} fill={m.color} stroke="white" strokeWidth="2" />
                })}
              </g>
            )
          })()}
        </g>

        {/* Tooltip */}
        {hovD && (() => {
          const x = xPx(hovered, n)
          const tooltipX = x > P.left + IW - 180 ? x - 170 : x + 10
          const lines = [
            { label: formatEpochFull(hovD.epoch), val: '', color: '#555', bold: true },
            ...activeLeftMetrics.map(m => {
              const v = hovD[m.key]
              return v != null ? { label: m.label, val: (m.format || formatLabel)(v), color: m.color } : null
            }).filter(Boolean),
            ...activeRightMetrics.map(m => {
              const v = hovD[m.key]
              return v != null ? { label: m.label, val: (m.format || formatLabel)(v), color: m.color } : null
            }).filter(Boolean),
            ...activeFlags.filter(f => f.style === 'line').map(f => {
              const v = hovD[f.key]
              if (!v || (f.trueOnly && v !== true)) return null
              return { label: f.trueLabel, val: '', color: f.trueColor, bold: false }
            }).filter(Boolean),
          ]
          const tw = 160, th = lines.length * 18 + 14
          const firstLv = primaryLeft != null ? (hovD[primaryLeft.key] ?? lRange.min) : lRange.min
          const ty = Math.max(P.top, Math.min(P.top + innerH - th, yL(isFinite(firstLv) ? firstLv : lRange.min) - th / 2))
          return (
            <g>
              <rect x={tooltipX} y={ty} width={tw} height={th} fill="rgba(33,37,41,0.92)" rx="5" />
              {lines.map((ln, li) => (
                <text key={li} x={tooltipX + 10} y={ty + 14 + li * 18} fontSize="11" fill={ln.color} fontWeight={ln.bold ? '700' : '400'}>
                  {ln.label}{ln.val ? `: ${ln.val}` : ''}
                </text>
              ))}
            </g>
          )
        })()}
      </svg>

      {(flags || []).length > 0 && (
        <div className="obs-flag-legend">
          {(flags || []).map((f, fi) => (
            <span key={fi} style={f.tbd ? { color: '#bdc3c7' } : {}}>
              {f.style === 'line'
                ? <span className="obs-flag-line" style={{ background: f.tbd ? '#bdc3c7' : f.trueColor }} />
                : <span className="obs-flag-dot" style={{ background: f.tbd ? '#bdc3c7' : f.trueColor }} />
              }
              {' '}{f.trueLabel || 'Flag: true'}{f.tbd ? ' (tbd)' : ''}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

const DELTA_TIME_OPTIONS = [
  { value: '1d',  label: '1 Day' },
  { value: '1w',  label: '1 Week' },
  { value: '1m',  label: '1 Month' },
  { value: '3m',  label: '3 Months' },
  { value: '6m',  label: '6 Months' },
  { value: '1y',  label: '1 Year' },
  { value: 'all', label: 'Show All' },
]

export default function ObservationDashboard({ initialNoradId, onInitialNoradIdConsumed }) {
  const [allowedSatellites, setAllowedSatellites] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const [selectedSat, setSelectedSat] = useState(null)
  const [noradInput, setNoradInput] = useState('')
  const [observations, setObservations] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [deltaTime, setDeltaTime] = useState('')
  const dropdownRef = useRef(null)

  useEffect(() => {
    apiFetch(API_ENDPOINTS.OBSERVATIONS + '/allowed-objects')
      .then(r => r.json())
      .then(d => setAllowedSatellites(d.data || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!initialNoradId || allowedSatellites.length === 0) return
    const id = parseInt(initialNoradId, 10)
    if (isNaN(id) || id <= 0) return
    const match = allowedSatellites.find(s => s.norad_id === id)
    setSelectedSat(match || { norad_id: id, name: null })
    setNoradInput(String(id))
    setSearchTerm(match?.name ? `${id} — ${match.name}` : String(id))
    loadObservations(id)
    if (onInitialNoradIdConsumed) onInitialNoradIdConsumed()
  }, [initialNoradId, allowedSatellites])

  useEffect(() => {
    function onClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const filteredSats = useMemo(() => {
    if (!searchTerm.trim()) return allowedSatellites.slice(0, 30)
    const q = searchTerm.toLowerCase()
    return allowedSatellites
      .filter(s =>
        String(s.norad_id).includes(q) ||
        (s.name && s.name.toLowerCase().includes(q))
      )
      .slice(0, 30)
  }, [allowedSatellites, searchTerm])

  const loadObservations = async (noradId) => {
    if (!noradId) return
    setLoading(true)
    setError(null)
    setObservations([])
    setDeltaTime('')
    try {
      const res = await apiFetch(`${API_ENDPOINTS.OBSERVATIONS}/${noradId}?limit=5000`)
      if (!res.ok) throw new Error(res.statusText)
      const d = await res.json()
      setObservations(d.data || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const allChartData = useMemo(() => buildChartData(observations), [observations])

  useEffect(() => {
    if (allChartData.length) {
      setDateFrom(allChartData[0].epoch?.substring(0, 16) || '')
      setDateTo(allChartData[allChartData.length - 1].epoch?.substring(0, 16) || '')
    } else {
      setDateFrom('')
      setDateTo('')
    }
  }, [allChartData])

  const chartData = useMemo(() => {
    return allChartData.filter(d => {
      if (!d.epoch) return true
      const ep = d.epoch.substring(0, 16)
      if (dateFrom && ep < dateFrom) return false
      if (dateTo && ep > dateTo) return false
      return true
    })
  }, [allChartData, dateFrom, dateTo])

  const handleDeltaTime = (delta) => {
    setDeltaTime(delta)
    if (!allChartData.length) return
    const lastEpoch = allChartData[allChartData.length - 1]?.epoch
    if (!lastEpoch) return
    if (!delta || delta === 'all') {
      setDateFrom(allChartData[0]?.epoch?.substring(0, 16) || '')
      setDateTo(lastEpoch.substring(0, 16))
      return
    }
    const last = new Date(lastEpoch)
    const from = new Date(last)
    switch (delta) {
      case '1d': from.setDate(from.getDate() - 1); break
      case '1w': from.setDate(from.getDate() - 7); break
      case '1m': from.setMonth(from.getMonth() - 1); break
      case '3m': from.setMonth(from.getMonth() - 3); break
      case '6m': from.setMonth(from.getMonth() - 6); break
      case '1y': from.setFullYear(from.getFullYear() - 1); break
    }
    setDateFrom(from.toISOString().substring(0, 16))
    setDateTo(last.toISOString().substring(0, 16))
  }

  const handleSelectSat = (sat) => {
    setSelectedSat(sat)
    setSearchTerm(sat.name ? `${sat.norad_id} — ${sat.name}` : String(sat.norad_id))
    setNoradInput(String(sat.norad_id))
    setShowDropdown(false)
    loadObservations(sat.norad_id)
  }

  const handleNoradSearch = () => {
    const id = parseInt(noradInput.trim(), 10)
    if (!isNaN(id) && id > 0) {
      const match = allowedSatellites.find(s => s.norad_id === id)
      setSelectedSat(match || { norad_id: id, name: null })
      loadObservations(id)
    }
  }

  const summaryStats = useMemo(() => {
    if (!chartData.length) return null
    const healthVals = chartData.map(d => d.health).filter(v => v != null && isFinite(v))
    const anomalyCount = chartData.filter(d => d.thermalAnomaly === true).length
    const maneuverCount = chartData.filter(d => d.manFlag === true).length
    const first = chartData[0]?.epoch
    const last = chartData[chartData.length - 1]?.epoch
    return {
      total: chartData.length,
      avgHealth: healthVals.length ? healthVals.reduce((a, b) => a + b, 0) / healthVals.length : null,
      minHealth: healthVals.length ? Math.min(...healthVals) : null,
      anomalyCount,
      maneuverCount,
      first,
      last,
    }
  }, [chartData])

  function healthScoreColor(v) {
    if (v == null) return '#7f8c8d'
    if (v >= 80) return '#27ae60'
    if (v >= 60) return '#f39c12'
    if (v >= 40) return '#e67e22'
    return '#e74c3c'
  }

  return (
    <div className="obs-dashboard">
      {/* Header / Selector */}
      <div className="obs-dashboard-header">
        <div className="obs-dashboard-title">
          <h2>Observation Dashboard</h2>
          <p>Select a satellite to visualize multi-domain sensor observations over time</p>
        </div>

        <div className="obs-selector-area">
          {/* Satellite dropdown */}
          {allowedSatellites.length > 0 && (
            <div className="obs-search-group">
              <label>Select Object</label>
              <select
                className="obs-sat-select"
                value={selectedSat?.norad_id || ''}
                onChange={e => {
                  const id = parseInt(e.target.value, 10)
                  const sat = allowedSatellites.find(s => s.norad_id === id)
                  if (sat) handleSelectSat(sat)
                }}
              >
                <option value="">— Choose an object —</option>
                {allowedSatellites.map(s => (
                  <option key={s.norad_id} value={s.norad_id}>
                    {s.norad_id} — {s.name || 'Unknown'}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="obs-selector-divider">or</div>

          {/* Name/search selector */}
          <div className="obs-search-group" ref={dropdownRef}>
            <label>Search by Name</label>
            <input
              className="obs-search-input"
              type="text"
              placeholder="Satellite name…"
              value={searchTerm}
              onChange={e => { setSearchTerm(e.target.value); setShowDropdown(true) }}
              onFocus={() => setShowDropdown(true)}
            />
            {showDropdown && filteredSats.length > 0 && (
              <div className="obs-dropdown">
                {filteredSats.map(s => (
                  <div
                    key={s.norad_id}
                    className="obs-dropdown-item"
                    onMouseDown={() => handleSelectSat(s)}
                  >
                    <span className="obs-dd-norad">{s.norad_id}</span>
                    <span className="obs-dd-name">{s.name || '—'}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="obs-selector-divider">or</div>

          {/* NORAD ID direct input */}
          <div className="obs-search-group">
            <label>NORAD ID</label>
            <div className="obs-norad-row">
              <input
                className="obs-norad-input"
                type="number"
                placeholder="e.g. 25544"
                value={noradInput}
                onChange={e => setNoradInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleNoradSearch()}
              />
              <button className="obs-load-btn" onClick={handleNoradSearch} disabled={loading || !noradInput}>
                Load
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="obs-dashboard-body">
        {!selectedSat && !loading && (
          <div className="obs-empty-state">
            <div className="obs-empty-icon">🛰</div>
            <h3>No satellite selected</h3>
            <p>Search for a satellite by name or enter a NORAD ID to load its observation data.</p>
            {allowedSatellites.length > 0 && (
              <p className="obs-empty-hint">{allowedSatellites.length} satellites have observations enabled.</p>
            )}
          </div>
        )}

        {loading && (
          <div className="obs-loading">
            <div className="obs-spinner" />
            <p>Loading observations…</p>
          </div>
        )}

        {error && !loading && (
          <div className="obs-error">
            <strong>Error:</strong> {error}
          </div>
        )}

        {!loading && !error && selectedSat && observations.length === 0 && (
          <div className="obs-empty-state">
            <div className="obs-empty-icon">📭</div>
            <h3>No observations found</h3>
            <p>No observation records are stored for NORAD ID {selectedSat.norad_id}.</p>
          </div>
        )}

        {!loading && chartData.length > 0 && summaryStats && (
          <>
            {/* Summary cards */}
            <div className="obs-summary-row">
              <div className="obs-stat-card">
                <div className="obs-stat-label">Total Observations</div>
                <div className="obs-stat-value">{summaryStats.total}</div>
              </div>
              <div className="obs-stat-card">
                <div className="obs-stat-label">Avg Health Score</div>
                <div className="obs-stat-value" style={{ color: healthScoreColor(summaryStats.avgHealth) }}>
                  {summaryStats.avgHealth != null ? summaryStats.avgHealth.toFixed(1) : '—'}
                </div>
              </div>
              <div className="obs-stat-card">
                <div className="obs-stat-label">Min Health Score</div>
                <div className="obs-stat-value" style={{ color: healthScoreColor(summaryStats.minHealth) }}>
                  {summaryStats.minHealth != null ? summaryStats.minHealth.toFixed(1) : '—'}
                </div>
              </div>
              <div className="obs-stat-card">
                <div className="obs-stat-label">Thermal Anomalies</div>
                <div className="obs-stat-value" style={{ color: summaryStats.anomalyCount > 0 ? '#e74c3c' : '#27ae60' }}>
                  {summaryStats.anomalyCount}
                </div>
              </div>
              <div className="obs-stat-card">
                <div className="obs-stat-label">Maneuver Flags</div>
                <div className="obs-stat-value" style={{ color: summaryStats.maneuverCount > 0 ? '#e67e22' : '#27ae60' }}>
                  {summaryStats.maneuverCount}
                </div>
              </div>
              <div className="obs-stat-card obs-stat-card--deltatime">
                <div className="obs-stat-label">Delta Time</div>
                <select
                  className="obs-deltatime-select"
                  value={deltaTime}
                  onChange={e => handleDeltaTime(e.target.value)}
                >
                  <option value="">— Select range —</option>
                  {DELTA_TIME_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              <div className="obs-stat-card obs-stat-card--wide obs-stat-card--daterange">
                <div className="obs-stat-label">Date Range</div>
                <div className="obs-daterange-inputs">
                  <input
                    type="datetime-local"
                    className="obs-date-input"
                    value={dateFrom}
                    onChange={e => { setDateFrom(e.target.value); setDeltaTime('') }}
                  />
                  <span className="obs-date-arrow">→</span>
                  <input
                    type="datetime-local"
                    className="obs-date-input"
                    value={dateTo}
                    onChange={e => { setDateTo(e.target.value); setDeltaTime('') }}
                  />
                </div>
              </div>
            </div>

            {/* Metadata breakdown */}
            {(() => {
              const modes = [...new Set(chartData.map(d => d.observationMode).filter(Boolean))]
              const sensors = [...new Set(chartData.map(d => d.sensorsActive).filter(Boolean))]
              const illuminations = [...new Set(chartData.map(d => d.illumination).filter(Boolean))]
              const passes = [...new Set(chartData.map(d => d.passId).filter(Boolean))]
              if (!modes.length && !sensors.length && !illuminations.length && !passes.length) return null
              return (
                <div className="obs-meta-breakdown">
                  {passes.length > 0 && (
                    <div className="obs-meta-group">
                      <span className="obs-meta-label">Passes ({passes.length}):</span>
                      <span className="obs-meta-values">{passes.slice(0, 8).join(', ')}{passes.length > 8 ? ` +${passes.length - 8} more` : ''}</span>
                    </div>
                  )}
                  {modes.length > 0 && (
                    <div className="obs-meta-group">
                      <span className="obs-meta-label">Observation Modes:</span>
                      <span className="obs-meta-values">{modes.join(', ')}</span>
                    </div>
                  )}
                  {sensors.length > 0 && (
                    <div className="obs-meta-group">
                      <span className="obs-meta-label">Sensors Active:</span>
                      <span className="obs-meta-values">{sensors.join(', ')}</span>
                    </div>
                  )}
                  {illuminations.length > 0 && (
                    <div className="obs-meta-group">
                      <span className="obs-meta-label">Illumination:</span>
                      <span className="obs-meta-values">{illuminations.join(', ')}</span>
                    </div>
                  )}
                </div>
              )
            })()}

            {/* Charts grid */}
            <div className="obs-charts-grid">
              {ANALYTICS_CONFIG
                .filter(cfg => chartData.some(cfg.hasData))
                .map(cfg => <TimeSeriesChart key={cfg.id} {...cfg} data={chartData} />)
              }
            </div>
          </>
        )}
      </div>
    </div>
  )
}

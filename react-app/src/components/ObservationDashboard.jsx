import { useState, useEffect, useMemo, useRef } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
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

function buildLinePath(data, keyFn, xFn, yFn, minV, maxV) {
  let path = ''
  let started = false
  data.forEach((d, i) => {
    const v = keyFn(d)
    if (v == null || !isFinite(v)) { started = false; return }
    const x = xFn(i, data.length).toFixed(1)
    const y = yFn(v, minV, maxV).toFixed(1)
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

function TimeSeriesChart({
  title, subtitle, data, id,
  left,   // { key, label, color, format? }
  right,  // { key, label, color, format? } | null
  extra,  // [{ key, label, color }] additional left-axis lines
  flags,  // { key, trueColor, falseColor } | null  — dots on x-axis
  height = SVG_H,
}) {
  const [hovered, setHovered] = useState(null)
  const n = data.length

  const leftVals  = data.map(d => d[left.key])
  const rightVals = right ? data.map(d => d[right.key]) : []
  const extraVals = (extra || []).map(e => data.map(d => d[e.key]))

  const lRange = niceRange(leftVals)
  const rRange = right ? niceRange(rightVals) : null

  const lTicks = niceTicks(lRange.min, lRange.max)
  const rTicks = rRange ? niceTicks(rRange.min, rRange.max) : []

  const innerH = height - P.top - P.bottom
  function yL(v) { return P.top + innerH - ((v - lRange.min) / (lRange.max - lRange.min)) * innerH }
  function yR(v) { return P.top + innerH - ((v - rRange.min) / (rRange.max - rRange.min)) * innerH }

  const gradId = `grad-${id}`
  const hasLeftData = leftVals.some(v => v != null && isFinite(v))
  const hasRightData = rightVals.some(v => v != null && isFinite(v))

  const labelStep = n > 20 ? Math.ceil(n / 12) : n > 10 ? 2 : 1

  const hovD = hovered != null ? data[hovered] : null

  return (
    <div className="obs-chart-card">
      <div className="obs-chart-header">
        <h3>{title}</h3>
        {subtitle && <span className="obs-chart-subtitle">{subtitle}</span>}
      </div>
      <div className="obs-chart-legend">
        <span className="obs-legend-item" style={{ color: left.color }}>
          <span className="obs-legend-dot" style={{ background: left.color }} />
          {left.label}
        </span>
        {(extra || []).map(e => (
          <span key={e.key} className="obs-legend-item" style={{ color: e.color }}>
            <span className="obs-legend-dot" style={{ background: e.color }} />
            {e.label}
          </span>
        ))}
        {right && (
          <span className="obs-legend-item obs-legend-right" style={{ color: right.color }}>
            <span className="obs-legend-dot obs-legend-dot-dashed" style={{ background: right.color }} />
            {right.label} (→)
          </span>
        )}
      </div>

      <svg
        viewBox={`0 0 ${SVG_W} ${height}`}
        className="obs-svg"
        onMouseLeave={() => setHovered(null)}
      >
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={left.color} stopOpacity="0.25" />
            <stop offset="100%" stopColor={left.color} stopOpacity="0.02" />
          </linearGradient>
          <clipPath id={`clip-${id}`}>
            <rect x={P.left} y={P.top} width={IW} height={innerH} />
          </clipPath>
        </defs>

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
            textAnchor="end" fontSize="11" fill={left.color}
          >
            {formatLabel(t)}
          </text>
        ))}

        {/* Left axis label */}
        <text
          x={20} y={P.top + innerH / 2}
          textAnchor="middle" fontSize="12" fontWeight="600"
          fill={left.color}
          transform={`rotate(-90, 20, ${P.top + innerH / 2})`}
        >
          {left.label}
        </text>

        {/* Right Y axis */}
        {right && hasRightData && <>
          {rTicks.map((t, ti) => (
            <text
              key={ti}
              x={P.left + IW + 8} y={yR(t) + 4}
              textAnchor="start" fontSize="11" fill={right.color}
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
            fill={right.color}
            transform={`rotate(90, ${SVG_W - 14}, ${P.top + innerH / 2})`}
          >
            {right.label}
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

        {/* Flag dots at bottom */}
        {flags && data.map((d, i) => {
          const v = d[flags.key]
          if (v == null) return null
          const col = v ? (flags.trueColor || '#e74c3c') : (flags.falseColor || '#2ecc71')
          return (
            <circle
              key={i}
              cx={xPx(i, n)} cy={P.top + innerH + 32}
              r={4} fill={col} opacity={0.8}
            />
          )
        })}

        {/* Axes */}
        <line x1={P.left} y1={P.top} x2={P.left} y2={P.top + innerH} stroke="#bdc3c7" strokeWidth="1.5" />
        <line x1={P.left} y1={P.top + innerH} x2={P.left + IW} y2={P.top + innerH} stroke="#bdc3c7" strokeWidth="1.5" />

        <g clipPath={`url(#clip-${id})`}>
          {/* Area fill for primary series */}
          {hasLeftData && (() => {
            const linePts = data
              .map((d, i) => {
                const v = d[left.key]
                if (v == null || !isFinite(v)) return null
                return { x: xPx(i, n), y: yL(v) }
              })
              .filter(Boolean)
            if (!linePts.length) return null
            const linePath2 = linePts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
            const areaPath = `${linePath2} L${linePts[linePts.length - 1].x.toFixed(1)},${P.top + innerH} L${linePts[0].x.toFixed(1)},${P.top + innerH} Z`
            return <path d={areaPath} fill={`url(#${gradId})`} />
          })()}

          {/* Primary left series line */}
          {hasLeftData && (() => {
            const path = buildLinePath(data, d => d[left.key], xPx, yL, lRange.min, lRange.max)
            return <path d={path} fill="none" stroke={left.color} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
          })()}

          {/* Extra left-axis lines */}
          {(extra || []).map((e, ei) => {
            const path = buildLinePath(data, d => d[e.key], xPx, yL, lRange.min, lRange.max)
            return <path key={ei} d={path} fill="none" stroke={e.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
          })}

          {/* Right axis line (dashed) */}
          {right && hasRightData && (() => {
            const path = buildLinePath(data, d => d[right.key], xPx, yR, rRange.min, rRange.max)
            return <path d={path} fill="none" stroke={right.color} strokeWidth="2" strokeDasharray="5,3" strokeLinejoin="round" strokeLinecap="round" />
          })()}

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
            const lv = d[left.key]
            const rv = right ? d[right.key] : null
            const x = xPx(hovered, n)
            return (
              <g>
                <line x1={x} y1={P.top} x2={x} y2={P.top + innerH} stroke="#bdc3c7" strokeWidth="1" strokeDasharray="4,2" />
                {lv != null && isFinite(lv) && (
                  <circle cx={x} cy={yL(lv)} r={5} fill={left.color} stroke="white" strokeWidth="2" />
                )}
                {rv != null && isFinite(rv) && (
                  <circle cx={x} cy={yR(rv)} r={5} fill={right.color} stroke="white" strokeWidth="2" />
                )}
                {(extra || []).map((e, ei) => {
                  const ev = d[e.key]
                  if (ev == null || !isFinite(ev)) return null
                  return <circle key={ei} cx={x} cy={yL(ev)} r={4} fill={e.color} stroke="white" strokeWidth="2" />
                })}
              </g>
            )
          })()}
        </g>

        {/* Tooltip */}
        {hovD && (() => {
          const lv = hovD[left.key]
          const rv = right ? hovD[right.key] : null
          const x = xPx(hovered, n)
          const tooltipX = x > P.left + IW - 180 ? x - 170 : x + 10
          const lFmt = left.format || formatLabel
          const rFmt = right?.format || formatLabel
          const lines = [
            { label: formatEpochFull(hovD.epoch), val: '', color: '#555', bold: true },
            ...(lv != null ? [{ label: left.label, val: lFmt(lv), color: left.color }] : []),
            ...((extra || []).map(e => {
              const ev = hovD[e.key]
              return ev != null ? { label: e.label, val: formatLabel(ev), color: e.color } : null
            }).filter(Boolean)),
            ...(rv != null ? [{ label: right.label, val: rFmt(rv), color: right.color }] : []),
          ]
          const tw = 160, th = lines.length * 18 + 14
          const ty = Math.max(P.top, Math.min(P.top + innerH - th, yPx(lv ?? 0, lRange.min, lRange.max) - th / 2))
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

      {flags && (
        <div className="obs-flag-legend">
          <span><span className="obs-flag-dot" style={{ background: flags.trueColor || '#e74c3c' }} /> {flags.trueLabel || 'Flag: true'}</span>
          <span><span className="obs-flag-dot" style={{ background: flags.falseColor || '#2ecc71' }} /> {flags.falseLabel || 'Flag: false'}</span>
        </div>
      )}
    </div>
  )
}

function HealthScoreChart({ data }) {
  const [hovered, setHovered] = useState(null)
  const n = data.length
  const vals = data.map(d => d.health).filter(v => v != null && isFinite(v))
  if (!vals.length) return <div className="obs-no-data">No health score data</div>

  const height = SVG_H

  function yH(v) {
    return P.top + (height - P.top - P.bottom) - ((v - 0) / 100) * (height - P.top - P.bottom)
  }

  const ticks = [0, 20, 40, 60, 80, 100]
  const gradId = 'health-grad'
  const labelStep = n > 20 ? Math.ceil(n / 12) : n > 10 ? 2 : 1
  const innerH = height - P.top - P.bottom

  function healthColor(v) {
    if (v == null) return '#bdc3c7'
    if (v >= 80) return '#27ae60'
    if (v >= 60) return '#f39c12'
    if (v >= 40) return '#e67e22'
    return '#e74c3c'
  }

  const linePts = data.map((d, i) => d.health != null && isFinite(d.health) ? { x: xPx(i, n), y: yH(d.health), v: d.health } : null)

  const linePath2 = linePts
    .filter(Boolean)
    .map((p, pi, arr) => `${pi === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(' ')

  const firstValid = linePts.find(Boolean)
  const lastValid = [...linePts].reverse().find(Boolean)
  const areaPath = firstValid && lastValid
    ? `${linePath2} L${lastValid.x.toFixed(1)},${P.top + innerH} L${firstValid.x.toFixed(1)},${P.top + innerH} Z`
    : ''

  const avg = vals.reduce((a, b) => a + b, 0) / vals.length

  return (
    <div className="obs-chart-card obs-chart-card--health">
      <div className="obs-chart-header">
        <h3>Health Score</h3>
        <span className="obs-chart-subtitle">Derived health score over time (0–100)</span>
        <span className="obs-health-avg" style={{ color: healthColor(avg) }}>
          Avg: {avg.toFixed(1)}
        </span>
      </div>

      <svg viewBox={`0 0 ${SVG_W} ${height}`} className="obs-svg" onMouseLeave={() => setHovered(null)}>
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#27ae60" stopOpacity="0.35" />
            <stop offset="60%" stopColor="#f39c12" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#e74c3c" stopOpacity="0.05" />
          </linearGradient>
          <clipPath id="clip-health">
            <rect x={P.left} y={P.top} width={IW} height={innerH} />
          </clipPath>
        </defs>

        {/* Threshold bands */}
        <rect x={P.left} y={yH(100)} width={IW} height={yH(80) - yH(100)} fill="rgba(39,174,96,0.06)" clipPath="url(#clip-health)" />
        <rect x={P.left} y={yH(80)} width={IW} height={yH(60) - yH(80)} fill="rgba(243,156,18,0.06)" clipPath="url(#clip-health)" />
        <rect x={P.left} y={yH(60)} width={IW} height={yH(40) - yH(60)} fill="rgba(230,126,34,0.06)" clipPath="url(#clip-health)" />
        <rect x={P.left} y={yH(40)} width={IW} height={yH(0) - yH(40)} fill="rgba(231,76,60,0.06)" clipPath="url(#clip-health)" />

        {ticks.map(t => (
          <g key={t}>
            <line x1={P.left} y1={yH(t)} x2={P.left + IW} y2={yH(t)} stroke="#eef0f3" strokeWidth="1" />
            <text x={P.left - 8} y={yH(t) + 4} textAnchor="end" fontSize="11" fill="#888">{t}</text>
          </g>
        ))}

        {data.map((d, i) => {
          if (i % labelStep !== 0 && i !== n - 1) return null
          return (
            <text key={i} x={xPx(i, n).toFixed(1)} y={P.top + innerH + 18} textAnchor="middle" fontSize="10" fill="#888">
              {formatEpoch(d.epoch)}
            </text>
          )
        })}

        <line x1={P.left} y1={P.top} x2={P.left} y2={P.top + innerH} stroke="#bdc3c7" strokeWidth="1.5" />
        <line x1={P.left} y1={P.top + innerH} x2={P.left + IW} y2={P.top + innerH} stroke="#bdc3c7" strokeWidth="1.5" />

        <text x={20} y={P.top + innerH / 2} textAnchor="middle" fontSize="12" fontWeight="600" fill="#27ae60"
          transform={`rotate(-90, 20, ${P.top + innerH / 2})`}>Health Score</text>

        <g clipPath="url(#clip-health)">
          {areaPath && <path d={areaPath} fill={`url(#${gradId})`} />}
          <path d={linePath2} fill="none" stroke="url(#health-line-grad)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />

          {data.map((d, i) => {
            if (d.health == null || !isFinite(d.health)) return null
            return (
              <rect
                key={i}
                x={xPx(i, n) - (n > 1 ? IW / n / 2 : IW / 2)}
                y={P.top} width={n > 1 ? IW / n : IW} height={innerH}
                fill="transparent"
                onMouseEnter={() => setHovered(i)}
              />
            )
          })}

          {hovered != null && data[hovered]?.health != null && (
            <g>
              <line x1={xPx(hovered, n)} y1={P.top} x2={xPx(hovered, n)} y2={P.top + innerH}
                stroke="#bdc3c7" strokeWidth="1" strokeDasharray="4,2" />
              <circle cx={xPx(hovered, n)} cy={yH(data[hovered].health)} r={6}
                fill={healthColor(data[hovered].health)} stroke="white" strokeWidth="2" />
            </g>
          )}
        </g>

        {hovered != null && data[hovered]?.health != null && (() => {
          const d = data[hovered]
          const x = xPx(hovered, n)
          const tooltipX = x > P.left + IW - 160 ? x - 150 : x + 10
          const ty = Math.max(P.top + 5, yH(d.health) - 40)
          return (
            <g>
              <rect x={tooltipX} y={ty} width={145} height={46} fill="rgba(33,37,41,0.92)" rx="5" />
              <text x={tooltipX + 10} y={ty + 16} fontSize="11" fill="#ccc" fontWeight="700">{formatEpochFull(d.epoch)}</text>
              <text x={tooltipX + 10} y={ty + 34} fontSize="12" fill={healthColor(d.health)} fontWeight="700">
                Score: {d.health.toFixed(2)}
              </text>
            </g>
          )
        })()}
      </svg>
    </div>
  )
}

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
    try {
      const res = await apiFetch(`${API_ENDPOINTS.OBSERVATIONS}/${noradId}?limit=500`)
      if (!res.ok) throw new Error(res.statusText)
      const d = await res.json()
      setObservations(d.data || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
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

  const allChartData = useMemo(() => {
    return [...observations]
      .sort((a, b) => (a.observation_epoch || '').localeCompare(b.observation_epoch || ''))
      .map(obs => ({
        epoch: obs.observation_epoch,
        health: obs.derived_health_score,
        roll: obs.attitude?.roll_deg,
        pitch: obs.attitude?.pitch_deg,
        yaw: obs.attitude?.yaw_deg,
        stability: obs.attitude?.stability_flag,
        temp: obs.thermal?.surface_temp_K,
        tempVariance: obs.thermal?.temp_variance_30d,
        thermalAnomaly: obs.thermal?.anomaly_flag,
        reflectivity: obs.material_signature?.reflectivity_index,
        materialConfidence: obs.material_signature?.material_confidence,
        range: obs.proximity_state?.range_km,
        velocity: obs.proximity_state?.relative_velocity_ms,
        deltaV: obs.maneuver_indicator?.delta_v_residual_ms,
        manConf: obs.maneuver_indicator?.maneuver_confidence,
        manFlag: obs.maneuver_indicator?.maneuver_flag ?? null,
        drift: obs.orbital_decay_indicator?.perigee_drift_km_per_day,
        estimatedPerigee: obs.orbital_decay_indicator?.estimated_perigee_km,
        mass: obs.estimated_mass_kg,
        spin: obs.spin_rate_rpm,
        passId: obs.pass_id,
        frameIndex: obs.frame_index,
        observationMode: obs.observation_mode,
        sensorsActive: obs.sensors_active,
        illumination: obs.illumination,
      }))
  }, [observations])

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

  const hasAttitude = chartData.some(d => d.roll != null || d.pitch != null || d.yaw != null)
  const hasThermal = chartData.some(d => d.temp != null)
  const hasMaterial = chartData.some(d => d.reflectivity != null)
  const hasProximity = chartData.some(d => d.range != null)
  const hasManeuver = chartData.some(d => d.deltaV != null)
  const hasDecay = chartData.some(d => d.drift != null || d.estimatedPerigee != null)

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
              <div className="obs-stat-card obs-stat-card--wide obs-stat-card--daterange">
                <div className="obs-stat-label">Date Range</div>
                <div className="obs-daterange-inputs">
                  <input
                    type="datetime-local"
                    className="obs-date-input"
                    value={dateFrom}
                    onChange={e => setDateFrom(e.target.value)}
                  />
                  <span className="obs-date-arrow">→</span>
                  <input
                    type="datetime-local"
                    className="obs-date-input"
                    value={dateTo}
                    onChange={e => setDateTo(e.target.value)}
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
              {/* Health score */}
              <HealthScoreChart data={chartData} />

              {/* Attitude */}
              {hasAttitude && (
                <TimeSeriesChart
                  id="attitude"
                  title="Attitude"
                  subtitle="Roll, Pitch, Yaw over time"
                  data={chartData}
                  left={{ key: 'roll', label: 'Roll (°)', color: COLORS.roll }}
                  extra={[
                    { key: 'pitch', label: 'Pitch (°)', color: COLORS.pitch },
                    { key: 'yaw', label: 'Yaw (°)', color: COLORS.yaw },
                  ]}
                  right={null}
                  flags={{ key: 'stability', trueColor: '#27ae60', falseColor: '#e74c3c', trueLabel: 'Stable', falseLabel: 'Unstable' }}
                />
              )}

              {/* Thermal */}
              {hasThermal && (
                <TimeSeriesChart
                  id="thermal"
                  title="Thermal"
                  subtitle="Surface temperature and variance"
                  data={chartData}
                  left={{ key: 'temp', label: 'Surface Temp (K)', color: COLORS.temp }}
                  right={{ key: 'tempVariance', label: 'Variance 30d', color: COLORS.tempVariance }}
                  flags={{ key: 'thermalAnomaly', trueColor: '#e74c3c', falseColor: '#2ecc71', trueLabel: 'Anomaly', falseLabel: 'Normal' }}
                />
              )}

              {/* Material Signature */}
              {hasMaterial && (
                <TimeSeriesChart
                  id="material"
                  title="Material Signature"
                  subtitle="Reflectivity index and confidence"
                  data={chartData}
                  left={{ key: 'reflectivity', label: 'Reflectivity Index', color: COLORS.reflectivity }}
                  right={{ key: 'materialConfidence', label: 'Confidence', color: COLORS.confidence }}
                />
              )}

              {/* Proximity State */}
              {hasProximity && (
                <TimeSeriesChart
                  id="proximity"
                  title="Proximity State"
                  subtitle="Range and relative velocity"
                  data={chartData}
                  left={{ key: 'range', label: 'Range (km)', color: COLORS.range }}
                  right={{ key: 'velocity', label: 'Rel. Velocity (m/s)', color: COLORS.velocity }}
                />
              )}

              {/* Maneuver Indicator */}
              {hasManeuver && (
                <TimeSeriesChart
                  id="maneuver"
                  title="Maneuver Indicator"
                  subtitle="ΔV residual and confidence"
                  data={chartData}
                  left={{ key: 'deltaV', label: 'ΔV Residual (m/s)', color: COLORS.deltaV }}
                  right={{ key: 'manConf', label: 'Confidence', color: COLORS.manConf }}
                  flags={{ key: 'manFlag', trueColor: '#e67e22', falseColor: '#2ecc71', trueLabel: 'Maneuver detected', falseLabel: 'No maneuver' }}
                />
              )}

              {/* Orbital Decay */}
              {hasDecay && (
                <TimeSeriesChart
                  id="orbital-decay"
                  title="Orbital Decay"
                  subtitle="Perigee drift rate and estimated perigee altitude"
                  data={chartData}
                  left={{ key: 'drift', label: 'Perigee Drift (km/d)', color: COLORS.drift }}
                  right={{ key: 'estimatedPerigee', label: 'Est. Perigee (km)', color: COLORS.perigee }}
                />
              )}

              {/* Mass / Spin — supplemental chart */}
              {chartData.some(d => d.mass != null || d.spin != null) && (
                <TimeSeriesChart
                  id="physical"
                  title="Physical Properties"
                  subtitle="Estimated mass and spin rate"
                  data={chartData}
                  left={{ key: 'mass', label: 'Mass (kg)', color: COLORS.mass }}
                  right={{ key: 'spin', label: 'Spin Rate (rpm)', color: COLORS.spin }}
                />
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

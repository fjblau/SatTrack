import { useState, useEffect, useCallback } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import './NextPassModal.css'

const HOURS_OPTIONS = [
  { label: '6 h', value: 6 },
  { label: '12 h', value: 12 },
  { label: '24 h', value: 24 },
  { label: '48 h', value: 48 },
  { label: '72 h', value: 72 },
]

function Stars({ count }) {
  return (
    <span className="pass-stars" title={`${count} star visibility`}>
      {Array.from({ length: 3 }, (_, i) => (
        <span key={i} className={i < count ? 'star filled' : 'star empty'}>★</span>
      ))}
    </span>
  )
}

function formatLocalTime(isoString) {
  if (!isoString) return '—'
  return new Date(isoString).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatDuration(seconds) {
  if (!seconds) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function formatAz(deg) {
  if (deg == null) return '—'
  return `${deg.toFixed(1)}°`
}

export default function NextPassModal({ satellite, noradId, onClose }) {
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [elevationM, setElevationM] = useState('0')
  const [minElevDeg, setMinElevDeg] = useState('10')
  const [hoursAhead, setHoursAhead] = useState(24)
  const [locating, setLocating] = useState(false)
  const [locError, setLocError] = useState(null)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const satelliteName = satellite?.canonical?.name || satellite?.['Object Name'] || `NORAD ${noradId}`

  useEffect(() => {
    const handleEscape = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setLocError('Geolocation is not supported by your browser')
      return
    }
    setLocating(true)
    setLocError(null)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude.toFixed(6))
        setLon(pos.coords.longitude.toFixed(6))
        if (pos.coords.altitude != null) {
          setElevationM(Math.round(pos.coords.altitude).toString())
        }
        setLocating(false)
      },
      (err) => {
        setLocError(`Could not get location: ${err.message}`)
        setLocating(false)
      }
    )
  }

  const fetchPasses = useCallback(async () => {
    const parsedLat = parseFloat(lat)
    const parsedLon = parseFloat(lon)
    if (isNaN(parsedLat) || isNaN(parsedLon)) {
      setError('Please enter a valid latitude and longitude.')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const params = new URLSearchParams({
        lat: parsedLat,
        lon: parsedLon,
        elevation_m: parseFloat(elevationM) || 0,
        min_elevation_deg: parseFloat(minElevDeg) || 10,
        hours_ahead: hoursAhead,
        num_passes: 10,
      })
      const res = await apiFetch(`${API_ENDPOINTS.TLE_PASSES(noradId)}?${params}`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setResult(data)
    } catch (err) {
      setError(err.message || 'Failed to fetch passes')
    } finally {
      setLoading(false)
    }
  }, [lat, lon, elevationM, minElevDeg, hoursAhead, noradId])

  const canSearch = lat !== '' && lon !== '' && !loading

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-content next-pass-modal">
        <div className="modal-header">
          <div>
            <h2>Next Pass</h2>
            <p className="modal-subtitle">{satelliteName}</p>
          </div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="np-controls">
            <div className="np-location-row">
              <button
                className="np-geo-button"
                onClick={useMyLocation}
                disabled={locating}
              >
                {locating ? 'Locating…' : '📍 Use my location'}
              </button>
              {locError && <span className="np-loc-error">{locError}</span>}
            </div>

            <div className="np-inputs">
              <label className="np-label">
                Latitude
                <input
                  className="np-input"
                  type="number"
                  step="0.0001"
                  min="-90"
                  max="90"
                  placeholder="e.g. 48.8566"
                  value={lat}
                  onChange={(e) => setLat(e.target.value)}
                />
              </label>
              <label className="np-label">
                Longitude
                <input
                  className="np-input"
                  type="number"
                  step="0.0001"
                  min="-180"
                  max="180"
                  placeholder="e.g. 2.3522"
                  value={lon}
                  onChange={(e) => setLon(e.target.value)}
                />
              </label>
              <label className="np-label">
                Elevation (m)
                <input
                  className="np-input np-input-sm"
                  type="number"
                  step="1"
                  min="0"
                  placeholder="0"
                  value={elevationM}
                  onChange={(e) => setElevationM(e.target.value)}
                />
              </label>
              <label className="np-label">
                Min elevation
                <input
                  className="np-input np-input-sm"
                  type="number"
                  step="1"
                  min="0"
                  max="89"
                  placeholder="10"
                  value={minElevDeg}
                  onChange={(e) => setMinElevDeg(e.target.value)}
                />
              </label>
              <label className="np-label">
                Search window
                <select
                  className="np-select"
                  value={hoursAhead}
                  onChange={(e) => setHoursAhead(Number(e.target.value))}
                >
                  {HOURS_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </label>
              <button
                className="np-search-button"
                onClick={fetchPasses}
                disabled={!canSearch}
              >
                Find Passes
              </button>
            </div>
          </div>

          {loading && (
            <div className="loading-message">
              <div className="spinner"></div>
              <p>Calculating passes…</p>
            </div>
          )}

          {error && (
            <div className="error-message">{error}</div>
          )}

          {result && !loading && (
            <div className="np-results">
              <div className="np-results-meta">
                <span>
                  Observer: <strong>{result.observer?.latitude}°, {result.observer?.longitude}°</strong>
                </span>
                {result.tle_age_hours != null && (
                  <span className={result.tle_age_hours > 168 ? 'np-stale-tle' : 'np-tle-age'}>
                    TLE age: {result.tle_age_hours.toFixed(0)} h
                    {result.tle_age_hours > 168 ? ' ⚠ stale' : ''}
                  </span>
                )}
              </div>

              {result.passes.length === 0 ? (
                <div className="np-empty">
                  No passes found in the next {hoursAhead} hours. Try increasing the search window or lowering the minimum elevation.
                </div>
              ) : (
                <div className="np-table-container">
                  <table className="np-table">
                    <thead>
                      <tr>
                        <th>Visibility</th>
                        <th>Rise (local)</th>
                        <th className="numeric">Max El°</th>
                        <th className="numeric">Duration</th>
                        <th className="numeric">Rise Az</th>
                        <th className="numeric">Set Az</th>
                        <th>Optical</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.passes.map((p, idx) => (
                        <tr key={idx} className={p.optically_visible ? 'np-row-optical' : ''}>
                          <td><Stars count={p.visibility_stars} /></td>
                          <td className="np-time">{formatLocalTime(p.rise?.time)}</td>
                          <td className="numeric np-elevation">{p.max_elevation_deg}°</td>
                          <td className="numeric">{formatDuration(p.duration_seconds)}</td>
                          <td className="numeric">{formatAz(p.rise?.azimuth_deg)}</td>
                          <td className="numeric">{formatAz(p.set?.azimuth_deg)}</td>
                          <td className="np-optical">
                            {p.optically_visible === true
                              ? <span className="np-visible-badge">🌙 Visible</span>
                              : p.optically_visible === false
                                ? <span className="np-equip-badge">Equipment</span>
                                : <span className="np-unknown-badge">—</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

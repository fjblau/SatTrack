import { useState, useEffect, useCallback, useRef } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import './NextPassModal.css'

const HOURS_OPTIONS = [
  { label: '6 h', value: 6 },
  { label: '12 h', value: 12 },
  { label: '24 h', value: 24 },
  { label: '48 h', value: 48 },
  { label: '72 h', value: 72 },
  { label: '4 days', value: 96 },
  { label: '5 days', value: 120 },
  { label: '1 week', value: 168 },
  { label: '10 days', value: 240 },
  { label: '2 weeks', value: 336 },
]

const SITES_STORAGE_KEY = 'kessler_ground_sites'

function loadSites() {
  try {
    return JSON.parse(localStorage.getItem(SITES_STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

function persistSites(sites) {
  localStorage.setItem(SITES_STORAGE_KEY, JSON.stringify(sites))
}

function genId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

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
  const [visibilityMode, setVisibilityMode] = useState('consumer')
  const [locating, setLocating] = useState(false)
  const [locError, setLocError] = useState(null)

  const [sites, setSites] = useState(loadSites)
  const [selectedSiteId, setSelectedSiteId] = useState('')
  const [showSaveForm, setShowSaveForm] = useState(false)
  const [newSiteName, setNewSiteName] = useState('')
  const [showManageSites, setShowManageSites] = useState(false)

  const [geoQuery, setGeoQuery] = useState('')
  const [geoResults, setGeoResults] = useState([])
  const [geoLoading, setGeoLoading] = useState(false)
  const [geoError, setGeoError] = useState(null)
  const geoDebounceRef = useRef(null)

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
        setSelectedSiteId('')
        setLocating(false)
      },
      (err) => {
        setLocError(`Could not get location: ${err.message}`)
        setLocating(false)
      }
    )
  }

  const handleSiteSelect = (e) => {
    const id = e.target.value
    setSelectedSiteId(id)
    if (!id) return
    const site = sites.find(s => s.id === id)
    if (site) {
      setLat(site.lat.toString())
      setLon(site.lon.toString())
      setElevationM(site.elevationM.toString())
    }
  }

  const handleSaveSite = () => {
    const name = newSiteName.trim()
    if (!name) return
    const parsedLat = parseFloat(lat)
    const parsedLon = parseFloat(lon)
    if (isNaN(parsedLat) || isNaN(parsedLon)) return
    const newSite = {
      id: genId(),
      name,
      lat: parsedLat,
      lon: parsedLon,
      elevationM: parseFloat(elevationM) || 0,
    }
    const updated = [...sites, newSite]
    setSites(updated)
    persistSites(updated)
    setSelectedSiteId(newSite.id)
    setNewSiteName('')
    setShowSaveForm(false)
  }

  const handleDeleteSite = (id) => {
    const updated = sites.filter(s => s.id !== id)
    setSites(updated)
    persistSites(updated)
    if (selectedSiteId === id) setSelectedSiteId('')
  }

  const handleGeoQueryChange = (e) => {
    const q = e.target.value
    setGeoQuery(q)
    setGeoResults([])
    setGeoError(null)
    if (geoDebounceRef.current) clearTimeout(geoDebounceRef.current)
    if (q.trim().length < 2) return
    geoDebounceRef.current = setTimeout(() => runGeoSearch(q.trim()), 400)
  }

  const runGeoSearch = async (q) => {
    setGeoLoading(true)
    setGeoError(null)
    try {
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=6&addressdetails=1`
      const res = await fetch(url, { headers: { 'Accept-Language': 'en' } })
      if (!res.ok) throw new Error(`Geocoder error ${res.status}`)
      const data = await res.json()
      setGeoResults(data)
      if (data.length === 0) setGeoError('No results found')
    } catch (err) {
      setGeoError(err.message || 'Search failed')
    } finally {
      setGeoLoading(false)
    }
  }

  const handleGeoSelect = (item) => {
    setLat(parseFloat(item.lat).toFixed(6))
    setLon(parseFloat(item.lon).toFixed(6))
    setElevationM('0')
    setSelectedSiteId('')
    setGeoQuery('')
    setGeoResults([])
    setGeoError(null)
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
        num_passes: 30,
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

  const getStars = (pass) =>
    visibilityMode === 'technical' ? pass.technical_stars : pass.visibility_stars

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
            <div className="np-sites-row">
              <div className="np-sites-select-group">
                <label className="np-label">
                  Saved Sites
                  <select
                    className="np-select np-sites-select"
                    value={selectedSiteId}
                    onChange={handleSiteSelect}
                  >
                    <option value="">— Custom —</option>
                    {sites.map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="np-sites-actions">
                <button
                  className="np-geo-button"
                  onClick={useMyLocation}
                  disabled={locating}
                >
                  {locating ? 'Locating…' : '📍 My location'}
                </button>
                {lat !== '' && lon !== '' && (
                  <button
                    className="np-save-site-button"
                    onClick={() => setShowSaveForm(v => !v)}
                    title="Save current coordinates as a named site"
                  >
                    💾 Save site
                  </button>
                )}
                {sites.length > 0 && (
                  <button
                    className="np-manage-button"
                    onClick={() => setShowManageSites(v => !v)}
                  >
                    Manage sites
                  </button>
                )}
              </div>
              {locError && <span className="np-loc-error np-loc-error-inline">{locError}</span>}
            </div>

            {showSaveForm && (
              <div className="np-save-form">
                <input
                  className="np-input np-site-name-input"
                  type="text"
                  placeholder="Site name (e.g. Berlin HQ)"
                  value={newSiteName}
                  onChange={e => setNewSiteName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleSaveSite() }}
                  autoFocus
                />
                <button
                  className="np-save-confirm-button"
                  onClick={handleSaveSite}
                  disabled={!newSiteName.trim()}
                >
                  Save
                </button>
                <button
                  className="np-cancel-button"
                  onClick={() => { setShowSaveForm(false); setNewSiteName('') }}
                >
                  Cancel
                </button>
              </div>
            )}

            {showManageSites && sites.length > 0 && (
              <div className="np-manage-sites">
                <div className="np-manage-title">Saved Sites</div>
                {sites.map(s => (
                  <div key={s.id} className="np-site-item">
                    <span className="np-site-item-name">{s.name}</span>
                    <span className="np-site-item-coords">
                      {s.lat.toFixed(4)}°, {s.lon.toFixed(4)}° · {s.elevationM} m
                    </span>
                    <button
                      className="np-site-delete"
                      onClick={() => handleDeleteSite(s.id)}
                      title="Delete site"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="np-geo-search">
              <div className="np-geo-search-row">
                <label className="np-label" style={{ flex: 1 }}>
                  Search by place name
                  <div className="np-geo-search-input-wrap">
                    <input
                      className="np-input np-geo-search-input"
                      type="text"
                      placeholder="e.g. Goldstone, ESA ESOC, Sydney"
                      value={geoQuery}
                      onChange={handleGeoQueryChange}
                      autoComplete="off"
                    />
                    {geoLoading && <span className="np-geo-spinner">…</span>}
                  </div>
                </label>
              </div>
              {(geoResults.length > 0 || geoError) && (
                <div className="np-geo-results">
                  {geoError && <div className="np-geo-no-results">{geoError}</div>}
                  {geoResults.map((item) => (
                    <button
                      key={item.place_id}
                      className="np-geo-result-item"
                      onClick={() => handleGeoSelect(item)}
                      type="button"
                    >
                      <span className="np-geo-result-name">
                        {item.address?.city || item.address?.town || item.address?.village || item.address?.county || item.name || item.display_name.split(',')[0]}
                      </span>
                      <span className="np-geo-result-detail">
                        {[item.address?.state, item.address?.country].filter(Boolean).join(', ')}
                        {' '}<span className="np-geo-result-coords">{parseFloat(item.lat).toFixed(3)}°, {parseFloat(item.lon).toFixed(3)}°</span>
                      </span>
                    </button>
                  ))}
                </div>
              )}
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
                  onChange={(e) => { setLat(e.target.value); setSelectedSiteId('') }}
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
                  onChange={(e) => { setLon(e.target.value); setSelectedSiteId('') }}
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

            <div className="np-visibility-toggle">
              <span className="np-toggle-label">Visibility scoring:</span>
              <button
                className={`np-toggle-btn ${visibilityMode === 'consumer' ? 'active' : ''}`}
                onClick={() => setVisibilityMode('consumer')}
                title="Consumer: higher elevation = more stars (clearer sightline)"
              >
                Consumer
              </button>
              <button
                className={`np-toggle-btn ${visibilityMode === 'technical' ? 'active' : ''}`}
                onClick={() => setVisibilityMode('technical')}
                title="Technical: 30–60° elevation is optimal (best RF link margin + manageable tracking rate)"
              >
                Technical RF
              </button>
              {visibilityMode === 'technical' && (
                <span className="np-toggle-hint">★★★ = 30–60° · ★★ = 15–29° or 61–80° · ★ = &lt;15° or &gt;80°</span>
              )}
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
                  Observer: <strong>
                    {selectedSiteId
                      ? sites.find(s => s.id === selectedSiteId)?.name + ' — '
                      : ''}
                    {result.observer?.latitude}°, {result.observer?.longitude}°
                  </strong>
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
                        <th title={visibilityMode === 'technical' ? 'Technical RF score: 30–60° optimal' : 'Consumer score: higher = better'}>
                          {visibilityMode === 'technical' ? 'RF Quality' : 'Visibility'}
                        </th>
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
                          <td><Stars count={getStars(p)} /></td>
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

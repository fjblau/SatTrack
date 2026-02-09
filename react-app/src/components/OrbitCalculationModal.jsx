import { useState, useEffect } from 'react'
import './OrbitCalculationModal.css'

export default function OrbitCalculationModal({ satellite, tleData, onClose }) {
  const [interval, setInterval] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [orbitData, setOrbitData] = useState(null)
  const [showEciColumns, setShowEciColumns] = useState(false)

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose()
    }
    
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  useEffect(() => {
    if (satellite && tleData) {
      fetchOrbitData()
    }
  }, [satellite, tleData, interval])

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  const fetchOrbitData = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const noradId = satellite.canonical?.norad_cat_id || satellite._norad_id
      
      console.log('OrbitCalculationModal - satellite object:', satellite)
      console.log('OrbitCalculationModal - extracted NORAD ID:', noradId)
      
      if (!noradId) {
        throw new Error('NORAD ID not found')
      }

      const apiUrl = `/api/v2/tle/${noradId}/orbit?interval_minutes=${interval}`
      console.log('OrbitCalculationModal - API URL:', apiUrl)

      const response = await fetch(apiUrl)
      
      console.log('OrbitCalculationModal - API response status:', response.status)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        console.log('OrbitCalculationModal - API error response:', errorData)
        
        if (response.status === 404) {
          throw new Error(`TLE data not found for NORAD ID ${noradId}`)
        }
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to calculate orbit`)
      }

      const data = await response.json()
      setOrbitData(data)
    } catch (err) {
      console.error('Error fetching orbit data:', err)
      setError(err.message || 'Failed to calculate orbit')
    } finally {
      setLoading(false)
    }
  }

  const formatDateTime = (isoString) => {
    if (!isoString) return 'N/A'
    const date = new Date(isoString)
    return date.toISOString().replace('T', ' ').substring(0, 19) + ' UTC'
  }

  const formatCoordinate = (value, decimals = 2) => {
    if (value === null || value === undefined) return 'N/A'
    return Number(value).toFixed(decimals)
  }

  if (!satellite || !tleData) return null

  const satelliteName = satellite.canonical?.name || satellite['Object Name'] || 'Unknown Satellite'

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-content orbit-modal">
        <div className="modal-header">
          <div>
            <h2>Orbit Calculation</h2>
            <p className="modal-subtitle">{satelliteName}</p>
          </div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <div className="modal-body">
          {loading ? (
            <div className="loading-message">
              <div className="spinner"></div>
              <p>Calculating orbital positions...</p>
            </div>
          ) : error ? (
            <div className="error-message">{error}</div>
          ) : orbitData ? (
            <div className="orbit-content">
              <div className="orbit-header-info">
                <div className="info-grid">
                  <div className="info-item">
                    <span className="info-label">NORAD ID:</span>
                    <span className="info-value">{orbitData.norad_id}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">TLE Epoch:</span>
                    <span className="info-value">{formatDateTime(orbitData.tle_epoch)}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Orbital Period:</span>
                    <span className="info-value">{formatCoordinate(orbitData.orbital_period_minutes, 2)} min</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Interval:</span>
                    <span className="info-value">
                      <select 
                        value={interval} 
                        onChange={(e) => setInterval(Number(e.target.value))}
                        className="interval-selector"
                      >
                        <option value={1}>1 minute</option>
                        <option value={2}>2 minutes</option>
                        <option value={5}>5 minutes</option>
                      </select>
                    </span>
                  </div>
                </div>

                {orbitData.tle_epoch_position && (
                  <div className="position-card tle-position">
                    <h3>Last TLE Position</h3>
                    <p className="position-note">Position at TLE epoch</p>
                    <div className="position-data">
                      <div className="position-row">
                        <span className="position-label">Time:</span>
                        <span className="position-value">{formatDateTime(orbitData.tle_epoch_position.timestamp)}</span>
                      </div>
                      <div className="position-row">
                        <span className="position-label">Latitude:</span>
                        <span className="position-value">{formatCoordinate(orbitData.tle_epoch_position.latitude, 2)}°</span>
                      </div>
                      <div className="position-row">
                        <span className="position-label">Longitude:</span>
                        <span className="position-value">{formatCoordinate(orbitData.tle_epoch_position.longitude, 2)}°</span>
                      </div>
                      <div className="position-row">
                        <span className="position-label">Altitude:</span>
                        <span className="position-value">{formatCoordinate(orbitData.tle_epoch_position.altitude_km, 1)} km</span>
                      </div>
                    </div>
                  </div>
                )}

                {orbitData.current_position && (
                  <div className="position-card current-position">
                    <h3>Estimated Current Position</h3>
                    <p className="position-note">Estimated position now</p>
                    <div className="position-data">
                      <div className="position-row">
                        <span className="position-label">Time:</span>
                        <span className="position-value">{formatDateTime(orbitData.current_position.timestamp)}</span>
                      </div>
                      <div className="position-row">
                        <span className="position-label">Latitude:</span>
                        <span className="position-value">{formatCoordinate(orbitData.current_position.latitude, 2)}°</span>
                      </div>
                      <div className="position-row">
                        <span className="position-label">Longitude:</span>
                        <span className="position-value">{formatCoordinate(orbitData.current_position.longitude, 2)}°</span>
                      </div>
                      <div className="position-row">
                        <span className="position-label">Altitude:</span>
                        <span className="position-value">{formatCoordinate(orbitData.current_position.altitude_km, 1)} km</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="table-section">
                <div className="table-header-row">
                  <h3>Future Orbit Positions (starting from current time)</h3>
                  <label className="eci-toggle">
                    <input 
                      type="checkbox" 
                      checked={showEciColumns}
                      onChange={(e) => setShowEciColumns(e.target.checked)}
                    />
                    <span>Show ECI coordinates</span>
                  </label>
                </div>
                
                <div className="orbit-table-container">
                  <table className="orbit-table">
                    <thead>
                      <tr>
                        <th>Time (UTC)</th>
                        <th className="numeric">Latitude (°)</th>
                        <th className="numeric">Longitude (°)</th>
                        <th className="numeric">Altitude (km)</th>
                        {showEciColumns && (
                          <>
                            <th className="numeric">ECI X (km)</th>
                            <th className="numeric">ECI Y (km)</th>
                            <th className="numeric">ECI Z (km)</th>
                          </>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {orbitData.future_positions && orbitData.future_positions.map((pos, idx) => (
                        <tr key={idx}>
                          <td>{formatDateTime(pos.timestamp)}</td>
                          <td className="numeric">{formatCoordinate(pos.latitude, 2)}</td>
                          <td className="numeric">{formatCoordinate(pos.longitude, 2)}</td>
                          <td className="numeric">{formatCoordinate(pos.altitude_km, 1)}</td>
                          {showEciColumns && (
                            <>
                              <td className="numeric">{formatCoordinate(pos.eci_x_km, 2)}</td>
                              <td className="numeric">{formatCoordinate(pos.eci_y_km, 2)}</td>
                              <td className="numeric">{formatCoordinate(pos.eci_z_km, 2)}</td>
                            </>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="loading-message">
              <p>No orbit data available</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

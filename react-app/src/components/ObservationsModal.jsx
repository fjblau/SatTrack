import { useState, useEffect } from 'react'
import './ObservationsModal.css'
import { API_ENDPOINTS } from '../config/constants'

const TOP_LEVEL_COLUMNS = [
  { key: 'observation_epoch', label: 'Epoch' },
  { key: 'source', label: 'Source' },
  { key: 'object_name', label: 'Object Name' },
  { key: 'object_type', label: 'Object Type' },
  { key: 'origin_country', label: 'Country' },
  { key: 'estimated_mass_kg', label: 'Mass (kg)' },
  { key: 'spin_rate_rpm', label: 'Spin (rpm)' },
  { key: 'derived_health_score', label: 'Health Score' },
]

const SECTION_COLUMNS = [
  {
    section: 'Attitude',
    columns: [
      { key: 'roll_deg', label: 'Roll (°)' },
      { key: 'pitch_deg', label: 'Pitch (°)' },
      { key: 'yaw_deg', label: 'Yaw (°)' },
      { key: 'stability_flag', label: 'Stability' },
    ],
  },
  {
    section: 'Thermal',
    columns: [
      { key: 'surface_temp_K', label: 'Temp (K)' },
      { key: 'temp_variance_30d', label: 'Variance 30d' },
      { key: 'anomaly_flag', label: 'Anomaly' },
    ],
  },
  {
    section: 'Material Signature',
    columns: [
      { key: 'reflectivity_index', label: 'Reflectivity' },
      { key: 'inferred_material', label: 'Material' },
      { key: 'confidence', label: 'Confidence' },
    ],
  },
  {
    section: 'Proximity State',
    columns: [
      { key: 'range_km', label: 'Range (km)' },
      { key: 'relative_velocity_ms', label: 'Velocity (m/s)' },
    ],
  },
  {
    section: 'Maneuver Indicator',
    columns: [
      { key: 'delta_v_residual_ms', label: 'ΔV Residual (m/s)' },
      { key: 'confidence', label: 'Confidence' },
      { key: 'flag', label: 'Flag' },
    ],
  },
  {
    section: 'Orbital Decay',
    columns: [
      { key: 'perigee_drift_km_per_day', label: 'Perigee Drift (km/d)' },
      { key: 'estimated_perigee_km', label: 'Est. Perigee (km)' },
    ],
  },
]

const SECTION_FIELD_KEYS = {
  'Attitude': 'attitude',
  'Thermal': 'thermal',
  'Material Signature': 'material_signature',
  'Proximity State': 'proximity_state',
  'Maneuver Indicator': 'maneuver_indicator',
  'Orbital Decay': 'orbital_decay_indicator',
}

function formatCell(value) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return value.toString()
    return value.toPrecision(4)
  }
  return String(value)
}

export default function ObservationsModal({ noradId, objectName, onClose }) {
  const [observations, setObservations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    if (!noradId) return

    const fetchObservations = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await fetch(`${API_ENDPOINTS.OBSERVATIONS}/${encodeURIComponent(noradId)}`)
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        const data = await response.json()
        setObservations(data.data || [])
        setTotal(data.total || 0)
      } catch (err) {
        setError(`Failed to load observations: ${err.message}`)
      } finally {
        setLoading(false)
      }
    }

    fetchObservations()
  }, [noradId])

  return (
    <div className="modal-overlay observations-overlay" onClick={onClose}>
      <div className="modal-content observations-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>Observational Data</h2>
            <p className="modal-subtitle">{objectName} &mdash; NORAD {noradId} &mdash; {total} observation{total !== 1 ? 's' : ''}</p>
          </div>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        <div className="observations-body">
          {loading && <p className="loading-message">Loading observations...</p>}
          {error && <p className="error-message">{error}</p>}
          {!loading && !error && observations.length === 0 && (
            <p className="loading-message">No observations found.</p>
          )}
          {!loading && !error && observations.length > 0 && (
            <div className="observations-table-wrapper">
              <table className="observations-table">
                <thead>
                  <tr>
                    {TOP_LEVEL_COLUMNS.map(col => (
                      <th key={col.key} rowSpan={2} className="th-top-level">{col.label}</th>
                    ))}
                    {SECTION_COLUMNS.map(sec => (
                      <th key={sec.section} colSpan={sec.columns.length} className="th-section">{sec.section}</th>
                    ))}
                  </tr>
                  <tr>
                    {SECTION_COLUMNS.map(sec =>
                      sec.columns.map((col, i) => (
                        <th key={`${sec.section}-${col.key}-${i}`} className="th-sub">{col.label}</th>
                      ))
                    )}
                  </tr>
                </thead>
                <tbody>
                  {observations.map((obs, rowIdx) => (
                    <tr key={obs._key || rowIdx} className={rowIdx % 2 === 0 ? 'row-even' : 'row-odd'}>
                      {TOP_LEVEL_COLUMNS.map(col => (
                        <td key={col.key}>{formatCell(obs[col.key])}</td>
                      ))}
                      {SECTION_COLUMNS.map(sec => {
                        const nested = obs[SECTION_FIELD_KEYS[sec.section]] || {}
                        return sec.columns.map((col, i) => (
                          <td key={`${sec.section}-${col.key}-${i}`}>{formatCell(nested[col.key])}</td>
                        ))
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

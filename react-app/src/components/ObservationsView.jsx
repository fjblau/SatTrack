import { useState, useEffect } from 'react'
import ObservationsFilters from './ObservationsFilters'
import './ObservationsModal.css'
import './ObservationsView.css'
import { API_ENDPOINTS, PAGINATION } from '../config/constants'

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

export default function ObservationsView() {
  const [filters, setFilters] = useState({})
  const [filterOptions, setFilterOptions] = useState({ sources: [], object_types: [], origin_countries: [] })
  const [page, setPage] = useState(0)
  const [observations, setObservations] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const limit = PAGINATION.DEFAULT_PAGE_SIZE

  useEffect(() => {
    fetchFilterOptions()
    fetchObservations(0)
  }, [])

  useEffect(() => {
    fetchObservations(0)
  }, [filters])

  const fetchFilterOptions = async () => {
    try {
      const response = await fetch(`${API_ENDPOINTS.OBSERVATIONS}/filter-options`)
      if (!response.ok) return
      const data = await response.json()
      setFilterOptions(data)
    } catch {
    }
  }

  const fetchObservations = async (pageNum = 0) => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams()

    if (filters.search) params.append('search', filters.search)
    if (filters.source) params.append('source', filters.source)
    if (filters.object_type) params.append('object_type', filters.object_type)
    if (filters.origin_country) params.append('origin_country', filters.origin_country)
    if (filters.has_anomaly) params.append('has_anomaly', 'true')
    if (filters.health_score_min !== undefined && filters.health_score_min !== '') {
      params.append('health_score_min', filters.health_score_min)
    }
    if (filters.health_score_max !== undefined && filters.health_score_max !== '') {
      params.append('health_score_max', filters.health_score_max)
    }
    if (filters.epoch_from) params.append('epoch_from', filters.epoch_from)
    if (filters.epoch_to) params.append('epoch_to', filters.epoch_to)

    params.append('skip', pageNum * limit)
    params.append('limit', limit)

    try {
      const response = await fetch(`${API_ENDPOINTS.OBSERVATIONS}?${params}`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const data = await response.json()
      setObservations(data.data || [])
      setTotal(data.total || 0)
      setPage(pageNum)
    } catch (err) {
      setError(`Failed to load observations: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters)
  }

  return (
    <div className="observations-view-container">
      <aside className="observations-view-sidebar">
        <ObservationsFilters
          filters={filters}
          filterOptions={filterOptions}
          onFilterChange={handleFilterChange}
        />
      </aside>

      <main className="observations-view-main">
        <div className="observations-view-header">
          <h2>Observational Data</h2>
          <p className="observations-view-subtitle">
            {total.toLocaleString()} observation{total !== 1 ? 's' : ''}
          </p>
        </div>

        {loading && <p className="observations-view-message">Loading observations...</p>}
        {error && <p className="observations-view-error">{error}</p>}
        {!loading && !error && observations.length === 0 && (
          <p className="observations-view-message">No observations found. Try adjusting your filters.</p>
        )}

        {!loading && !error && observations.length > 0 && (
          <>
            <div className="observations-table-wrapper observations-view-table-wrapper">
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

            {total > limit && (
              <div className="pagination">
                <button
                  onClick={() => fetchObservations(page - 1)}
                  disabled={page === 0}
                >
                  Previous
                </button>
                <span>Page {page + 1} of {Math.ceil(total / limit)}</span>
                <button
                  onClick={() => fetchObservations(page + 1)}
                  disabled={(page + 1) * limit >= total}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}

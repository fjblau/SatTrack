import apiFetch from '../utils/apiFetch'
import { useState, useEffect } from 'react'
import ObservationsFilters from './ObservationsFilters'
import './ObservationsModal.css'
import './ObservationsView.css'
import { API_ENDPOINTS, PAGINATION } from '../config/constants'

const TOP_LEVEL_COLUMNS = [
  { key: 'norad_id', label: 'NORAD', sortKey: 'norad_id' },
  { key: 'observation_epoch', label: 'Epoch', sortKey: 'observation_epoch' },
  { key: 'pass_id', label: 'Pass ID', sortKey: 'pass_id' },
  { key: 'frame_index', label: 'Frame', sortKey: 'frame_index' },
  { key: 'observation_mode', label: 'Mode', sortKey: 'observation_mode' },
  { key: 'sensors_active', label: 'Sensors', sortKey: 'sensors_active' },
  { key: 'illumination', label: 'Illumination', sortKey: 'illumination' },
  { key: 'source', label: 'Source', sortKey: 'source' },
  { key: 'object_name', label: 'Object Name', sortKey: 'object_name' },
  { key: 'object_type', label: 'Object Type', sortKey: 'object_type' },
  { key: 'origin_country', label: 'Country', sortKey: 'origin_country' },
  { key: 'estimated_mass_kg', label: 'Mass (kg)', sortKey: 'estimated_mass_kg' },
  { key: 'spin_rate_rpm', label: 'Spin (rpm)', sortKey: 'spin_rate_rpm' },
  { key: 'derived_health_score', label: 'Health Score', sortKey: 'derived_health_score' },
]

const SECTION_COLUMNS = [
  {
    section: 'Attitude',
    columns: [
      { key: 'roll_deg', label: 'Roll (°)', sortKey: 'attitude.roll_deg' },
      { key: 'pitch_deg', label: 'Pitch (°)', sortKey: 'attitude.pitch_deg' },
      { key: 'yaw_deg', label: 'Yaw (°)', sortKey: 'attitude.yaw_deg' },
      { key: 'stability_flag', label: 'Stability', sortKey: 'attitude.stability_flag' },
    ],
  },
  {
    section: 'Thermal',
    columns: [
      { key: 'surface_temp_K', label: 'Temp (K)', sortKey: 'thermal.surface_temp_K' },
      { key: 'temp_variance_30d', label: 'Variance 30d', sortKey: 'thermal.temp_variance_30d' },
      { key: 'anomaly_flag', label: 'Anomaly', sortKey: 'thermal.anomaly_flag' },
    ],
  },
  {
    section: 'Material Signature',
    columns: [
      { key: 'reflectivity_index', label: 'Reflectivity', sortKey: 'material_signature.reflectivity_index' },
      { key: 'inferred_material', label: 'Material', sortKey: 'material_signature.inferred_material' },
      { key: 'material_confidence', label: 'Confidence', sortKey: 'material_signature.material_confidence' },
    ],
  },
  {
    section: 'Proximity State',
    columns: [
      { key: 'range_km', label: 'Range (km)', sortKey: 'proximity_state.range_km' },
      { key: 'relative_velocity_ms', label: 'Velocity (m/s)', sortKey: 'proximity_state.relative_velocity_ms' },
    ],
  },
  {
    section: 'Maneuver Indicator',
    columns: [
      { key: 'delta_v_residual_ms', label: 'ΔV Residual (m/s)', sortKey: 'maneuver_indicator.delta_v_residual_ms' },
      { key: 'maneuver_confidence', label: 'Confidence', sortKey: 'maneuver_indicator.maneuver_confidence' },
      { key: 'maneuver_flag', label: 'Flag', sortKey: 'maneuver_indicator.maneuver_flag' },
    ],
  },
  {
    section: 'Orbital Decay',
    columns: [
      { key: 'perigee_drift_km_per_day', label: 'Perigee Drift (km/d)', sortKey: 'orbital_decay_indicator.perigee_drift_km_per_day' },
      { key: 'estimated_perigee_km', label: 'Est. Perigee (km)', sortKey: 'orbital_decay_indicator.estimated_perigee_km' },
    ],
  },
  {
    section: 'Location',
    computed: true,
    columns: [
      { key: 'latitude', label: 'Latitude (°)' },
      { key: 'longitude', label: 'Longitude (°)' },
      { key: 'altitude_km', label: 'Altitude (km)' },
      { key: 'inclination_degrees', label: 'Inclination (°)' },
      { key: 'eccentricity', label: 'Eccentricity' },
      { key: 'apogee_km', label: 'Apogee (km)' },
      { key: 'perigee_km', label: 'Perigee (km)' },
      { key: 'period_minutes', label: 'Period (min)' },
      { key: 'tle_epoch', label: 'TLE Epoch' },
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
  'Location': 'location',
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

const HEALTH_GRADIENT = [
  { stop: 0,   r: 0xFF, g: 0x06, b: 0x0D },
  { stop: 20,  r: 0xFF, g: 0x4E, b: 0x11 },
  { stop: 40,  r: 0xFF, g: 0x8E, b: 0x15 },
  { stop: 60,  r: 0xFA, g: 0xB7, b: 0x33 },
  { stop: 80,  r: 0xAC, g: 0xB3, b: 0x34 },
  { stop: 100, r: 0x69, g: 0xB3, b: 0x4C },
]

function healthScoreStyle(value) {
  if (value === null || value === undefined || typeof value !== 'number') return {}
  const score = Math.max(0, Math.min(100, value))
  let lo = HEALTH_GRADIENT[0], hi = HEALTH_GRADIENT[HEALTH_GRADIENT.length - 1]
  for (let i = 0; i < HEALTH_GRADIENT.length - 1; i++) {
    if (score >= HEALTH_GRADIENT[i].stop && score <= HEALTH_GRADIENT[i + 1].stop) {
      lo = HEALTH_GRADIENT[i]
      hi = HEALTH_GRADIENT[i + 1]
      break
    }
  }
  const t = (score - lo.stop) / (hi.stop - lo.stop)
  const r = Math.round(lo.r + t * (hi.r - lo.r))
  const g = Math.round(lo.g + t * (hi.g - lo.g))
  const b = Math.round(lo.b + t * (hi.b - lo.b))
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return {
    backgroundColor: `rgb(${r}, ${g}, ${b})`,
    color: luminance > 0.55 ? '#333' : '#fff',
    fontWeight: 600,
    borderRadius: '4px',
    padding: '2px 6px',
    display: 'inline-block',
    minWidth: '3rem',
    textAlign: 'center',
  }
}

export default function ObservationsView() {
  const [filters, setFilters] = useState({})
  const [filterOptions, setFilterOptions] = useState({ sources: [], object_types: [], origin_countries: [] })
  const [page, setPage] = useState(0)
  const [observations, setObservations] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sortBy, setSortBy] = useState('observation_epoch')
  const [sortOrder, setSortOrder] = useState('DESC')

  const limit = PAGINATION.DEFAULT_PAGE_SIZE

  useEffect(() => {
    fetchFilterOptions()
  }, [])

  useEffect(() => {
    fetchObservations(0)
  }, [filters, sortBy, sortOrder])

  const fetchFilterOptions = async () => {
    try {
      const response = await apiFetch(`${API_ENDPOINTS.OBSERVATIONS}/filter-options`)
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
    params.append('sort_by', sortBy)
    params.append('sort_order', sortOrder)

    try {
      const response = await apiFetch(`${API_ENDPOINTS.OBSERVATIONS}?${params}`)
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

  const handleSort = (colSortKey) => {
    if (sortBy === colSortKey) {
      setSortOrder(prev => prev === 'ASC' ? 'DESC' : 'ASC')
    } else {
      setSortBy(colSortKey)
      setSortOrder('ASC')
    }
  }

  const SortIndicator = ({ colSortKey }) => {
    if (sortBy !== colSortKey) return <span className="sort-indicator sort-indicator-inactive">↕</span>
    return <span className="sort-indicator sort-indicator-active">{sortOrder === 'ASC' ? '↑' : '↓'}</span>
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
                      <th
                        key={col.key}
                        rowSpan={2}
                        className="th-top-level th-sortable"
                        onClick={() => handleSort(col.sortKey)}
                      >
                        {col.label}
                        <SortIndicator colSortKey={col.sortKey} />
                      </th>
                    ))}
                    {SECTION_COLUMNS.map(sec => (
                      <th
                        key={sec.section}
                        colSpan={sec.columns.length}
                        className={sec.computed ? 'th-section th-section-computed' : 'th-section'}
                      >
                        {sec.section}
                      </th>
                    ))}
                  </tr>
                  <tr>
                    {SECTION_COLUMNS.map(sec =>
                      sec.columns.map((col, i) => (
                        <th
                          key={`${sec.section}-${col.key}-${i}`}
                          className={
                            sec.computed
                              ? 'th-sub th-sub-computed' + (col.sortKey ? ' th-sortable' : '')
                              : 'th-sub th-sortable'
                          }
                          onClick={col.sortKey ? () => handleSort(col.sortKey) : undefined}
                        >
                          {col.label}
                          {col.sortKey && <SortIndicator colSortKey={col.sortKey} />}
                        </th>
                      ))
                    )}
                  </tr>
                </thead>
                <tbody>
                  {observations.map((obs, rowIdx) => (
                    <tr key={obs._key || rowIdx} className={rowIdx % 2 === 0 ? 'row-even' : 'row-odd'}>
                      {TOP_LEVEL_COLUMNS.map(col => (
                        <td key={col.key}>
                          {col.key === 'derived_health_score'
                            ? <span style={healthScoreStyle(obs[col.key])}>{typeof obs[col.key] === 'number' ? obs[col.key].toFixed(2) : '—'}</span>
                            : formatCell(obs[col.key])}
                        </td>
                      ))}
                      {SECTION_COLUMNS.map(sec => {
                        const nested = obs[SECTION_FIELD_KEYS[sec.section]] || {}
                        return sec.columns.map((col, i) => {
                          const val = obs[col.key] !== undefined && obs[col.key] !== null
                            ? obs[col.key]
                            : nested[col.key]
                          return (
                            <td
                              key={`${sec.section}-${col.key}-${i}`}
                              className={sec.computed ? 'td-computed' : undefined}
                            >
                              {formatCell(val)}
                            </td>
                          )
                        })
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

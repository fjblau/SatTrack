import { useState, useRef, useCallback } from 'react'
import './Filters.css'
import './ObservationsFilters.css'

export default function ObservationsFilters({ filters, filterOptions, onFilterChange }) {
  const [localFilters, setLocalFilters] = useState(filters)
  const debounceRef = useRef(null)

  const handleChange = (key, value) => {
    const newFilters = { ...localFilters, [key]: value }
    setLocalFilters(newFilters)
    onFilterChange(newFilters)
  }

  const handleTextChange = useCallback((key, value) => {
    const newFilters = { ...localFilters, [key]: value }
    setLocalFilters(newFilters)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      onFilterChange(newFilters)
    }, 400)
  }, [localFilters, onFilterChange])

  const handleReset = () => {
    const reset = {}
    setLocalFilters(reset)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    onFilterChange(reset)
  }

  return (
    <div className="filters">
      <div className="filters-header">
        <h2>Filters</h2>
        <button className="reset-btn" onClick={handleReset}>Reset</button>
      </div>

      <div className="filter-group">
        <label htmlFor="obs-search">Object Name</label>
        <input
          id="obs-search"
          type="text"
          placeholder="Search by name..."
          value={localFilters.search || ''}
          onChange={(e) => handleTextChange('search', e.target.value)}
        />
      </div>

      <div className="filter-group">
        <label htmlFor="obs-source">Source</label>
        <select
          id="obs-source"
          value={localFilters.source || ''}
          onChange={(e) => handleChange('source', e.target.value)}
        >
          <option value="">All Sources</option>
          {(filterOptions.sources || []).map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="obs-object-type">Object Type</label>
        <select
          id="obs-object-type"
          value={localFilters.object_type || ''}
          onChange={(e) => handleChange('object_type', e.target.value)}
        >
          <option value="">All Types</option>
          {(filterOptions.object_types || []).map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="obs-country">Country</label>
        <select
          id="obs-country"
          value={localFilters.origin_country || ''}
          onChange={(e) => handleChange('origin_country', e.target.value)}
        >
          <option value="">All Countries</option>
          {(filterOptions.origin_countries || []).map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label>Health Score</label>
        <div className="range-inputs">
          <input
            type="number"
            placeholder="Min"
            min="0"
            max="100"
            value={localFilters.health_score_min !== undefined ? localFilters.health_score_min : ''}
            onChange={(e) => handleChange('health_score_min', e.target.value === '' ? undefined : parseFloat(e.target.value))}
          />
          <span>—</span>
          <input
            type="number"
            placeholder="Max"
            min="0"
            max="100"
            value={localFilters.health_score_max !== undefined ? localFilters.health_score_max : ''}
            onChange={(e) => handleChange('health_score_max', e.target.value === '' ? undefined : parseFloat(e.target.value))}
          />
        </div>
        <small>0 — 100</small>
      </div>

      <div className="filter-group">
        <label htmlFor="obs-epoch-from">Epoch From</label>
        <input
          id="obs-epoch-from"
          type="date"
          value={localFilters.epoch_from || ''}
          onChange={(e) => handleChange('epoch_from', e.target.value)}
        />
      </div>

      <div className="filter-group">
        <label htmlFor="obs-epoch-to">Epoch To</label>
        <input
          id="obs-epoch-to"
          type="date"
          value={localFilters.epoch_to || ''}
          onChange={(e) => handleChange('epoch_to', e.target.value)}
        />
      </div>

      <div className="filter-group">
        <label className="obs-checkbox-label">
          <input
            type="checkbox"
            checked={localFilters.has_anomaly || false}
            onChange={(e) => handleChange('has_anomaly', e.target.checked || undefined)}
          />
          Has Thermal Anomaly
        </label>
      </div>
    </div>
  )
}

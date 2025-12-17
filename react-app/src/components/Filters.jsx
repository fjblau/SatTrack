import { useState } from 'react'
import './Filters.css'

export default function Filters({ filters, filterOptions, onFilterChange }) {
  const [localFilters, setLocalFilters] = useState(filters)

  const handleChange = (key, value) => {
    const newFilters = { ...localFilters, [key]: value }
    setLocalFilters(newFilters)
    onFilterChange(newFilters)
  }

  const handleRangeChange = (key, value) => {
    const newFilters = { ...localFilters, [key]: value === '' ? undefined : parseFloat(value) }
    setLocalFilters(newFilters)
    onFilterChange(newFilters)
  }

  const handleReset = () => {
    const reset = {}
    setLocalFilters(reset)
    onFilterChange(reset)
  }

  return (
    <div className="filters">
      <div className="filters-header">
        <h2>Filters</h2>
        <button className="reset-btn" onClick={handleReset}>Reset</button>
      </div>

      <div className="filter-group">
        <label htmlFor="search">Search</label>
        <input
          id="search"
          type="text"
          placeholder="Registration or name..."
          value={localFilters.search || ''}
          onChange={(e) => handleChange('search', e.target.value)}
        />
      </div>

      <div className="filter-group">
        <label htmlFor="country">Country</label>
        <select
          id="country"
          value={localFilters.country || ''}
          onChange={(e) => handleChange('country', e.target.value)}
        >
          <option value="">All Countries</option>
          {filterOptions.countries?.map(country => (
            <option key={country} value={country}>{country}</option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="status">Status</label>
        <select
          id="status"
          value={localFilters.status || ''}
          onChange={(e) => handleChange('status', e.target.value)}
        >
          <option value="">All Statuses</option>
          {filterOptions.statuses?.map(status => (
            <option key={status} value={status}>{status}</option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="orbital-band">Orbital Band</label>
        <select
          id="orbital-band"
          value={localFilters.orbital_band || ''}
          onChange={(e) => handleChange('orbital_band', e.target.value)}
        >
          <option value="">All Orbital Bands</option>
          {filterOptions.orbital_bands?.map(band => (
            <option key={band} value={band}>{band}</option>
          ))}
        </select>
      </div>

      {filterOptions.apogee_range && (
        <div className="filter-group">
          <label>Apogee Range (km)</label>
          <div className="range-inputs">
            <input
              type="number"
              placeholder="Min"
              value={localFilters.apogee_min || ''}
              onChange={(e) => handleRangeChange('apogee_min', e.target.value)}
            />
            <span>—</span>
            <input
              type="number"
              placeholder="Max"
              value={localFilters.apogee_max || ''}
              onChange={(e) => handleRangeChange('apogee_max', e.target.value)}
            />
          </div>
          <small>{filterOptions.apogee_range[0].toFixed(0)} — {filterOptions.apogee_range[1].toFixed(0)} km</small>
        </div>
      )}

      {filterOptions.perigee_range && (
        <div className="filter-group">
          <label>Perigee Range (km)</label>
          <div className="range-inputs">
            <input
              type="number"
              placeholder="Min"
              value={localFilters.perigee_min || ''}
              onChange={(e) => handleRangeChange('perigee_min', e.target.value)}
            />
            <span>—</span>
            <input
              type="number"
              placeholder="Max"
              value={localFilters.perigee_max || ''}
              onChange={(e) => handleRangeChange('perigee_max', e.target.value)}
            />
          </div>
          <small>{filterOptions.perigee_range[0].toFixed(0)} — {filterOptions.perigee_range[1].toFixed(0)} km</small>
        </div>
      )}

      {filterOptions.inclination_range && (
        <div className="filter-group">
          <label>Inclination Range (°)</label>
          <div className="range-inputs">
            <input
              type="number"
              placeholder="Min"
              value={localFilters.inclination_min || ''}
              onChange={(e) => handleRangeChange('inclination_min', e.target.value)}
            />
            <span>—</span>
            <input
              type="number"
              placeholder="Max"
              value={localFilters.inclination_max || ''}
              onChange={(e) => handleRangeChange('inclination_max', e.target.value)}
            />
          </div>
          <small>{filterOptions.inclination_range[0].toFixed(2)}° — {filterOptions.inclination_range[1].toFixed(2)}°</small>
        </div>
      )}
    </div>
  )
}

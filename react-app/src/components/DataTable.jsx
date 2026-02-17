import './DataTable.css'
import { SATELLITE_STATUS, UI_TEXT, NUMBER_FORMATS } from '../config/constants'

export default function DataTable({ objects, selectedObject, onRowClick, loading, sortConfig, onSort }) {
  if (loading) {
    return <div className="loading">{UI_TEXT.LOADING}</div>
  }

  if (objects.length === 0) {
    return <div className="empty-state">{UI_TEXT.NO_OBJECTS_FOUND}</div>
  }

  const getSortIndicator = (column) => {
    const sortIndex = sortConfig.findIndex(s => s.column === column)
    if (sortIndex === -1) return null
    
    const sort = sortConfig[sortIndex]
    const arrow = sort.direction === 'asc' ? '↑' : '↓'
    const badge = sortConfig.length > 1 ? ` ${sortIndex + 1}` : ''
    
    return <span className="sort-indicator">{arrow}{badge}</span>
  }

  const handleSort = (column) => {
    if (onSort) {
      onSort(column)
    }
  }

  const columns = [
    { key: 'Identifier', label: 'Identifier' },
    { key: 'Object Name', label: 'Object Name' },
    { key: 'Country of Origin', label: 'Country of Origin' },
    { key: 'Date of Launch', label: 'Date of Launch' },
    { key: 'Status', label: 'Status' },
    { key: 'Orbital Band', label: 'Orbital Band' },
    { key: 'Congestion Risk', label: 'Congestion Risk' },
    { key: 'Apogee (km)', label: 'Apogee (km)', className: 'cell-number' },
    { key: 'Perigee (km)', label: 'Perigee (km)', className: 'cell-number' },
    { key: 'Inclination (degrees)', label: 'Inclination (°)', className: 'cell-number' },
    { key: 'Period (minutes)', label: 'Period (min)', className: 'cell-number' }
  ]

  return (
    <div className="data-table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map(col => (
              <th 
                key={col.key}
                className={`${col.className || ''} sortable`}
                onClick={() => handleSort(col.key)}
              >
                <div className="th-content">
                  <span>{col.label}</span>
                  {getSortIndicator(col.key)}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {objects.map((obj) => {
            const classNames = []
            if (selectedObject?.['Identifier'] === obj['Identifier']) {
              classNames.push('selected')
            }
            if (obj['Status'] === SATELLITE_STATUS.DECAYED || obj['Status'] === SATELLITE_STATUS.DEORBITED) {
              classNames.push('decayed')
            }
            return (
            <tr 
              key={obj['Identifier']}
              className={classNames.join(' ')}
              onClick={() => onRowClick(obj)}
            >
              <td className="cell-reg">{obj['Identifier']}</td>
              <td className="cell-name">{obj['Object Name'] || '—'}</td>
              <td>{obj['Country of Origin'] || '—'}</td>
              <td>{obj['Date of Launch'] || '—'}</td>
              <td>{obj['Status'] || '—'}</td>
              <td>{obj['Orbital Band'] || '—'}</td>
              <td>{obj['Congestion Risk'] || '—'}</td>
              <td className="cell-number">{obj['Apogee (km)'] ? obj['Apogee (km)'].toFixed(NUMBER_FORMATS.ORBITAL_DECIMAL_PLACES) : '—'}</td>
              <td className="cell-number">{obj['Perigee (km)'] ? obj['Perigee (km)'].toFixed(NUMBER_FORMATS.ORBITAL_DECIMAL_PLACES) : '—'}</td>
              <td className="cell-number">{obj['Inclination (degrees)'] ? obj['Inclination (degrees)'].toFixed(NUMBER_FORMATS.ORBITAL_DECIMAL_PLACES) : '—'}</td>
              <td className="cell-number">{obj['Period (minutes)'] ? obj['Period (minutes)'].toFixed(NUMBER_FORMATS.ORBITAL_DECIMAL_PLACES) : '—'}</td>
            </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

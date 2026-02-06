import './DataTable.css'
import { SATELLITE_STATUS, UI_TEXT, NUMBER_FORMATS } from '../config/constants'

export default function DataTable({ objects, selectedObject, onRowClick, loading }) {
  if (loading) {
    return <div className="loading">{UI_TEXT.LOADING}</div>
  }

  if (objects.length === 0) {
    return <div className="empty-state">{UI_TEXT.NO_OBJECTS_FOUND}</div>
  }

  return (
    <div className="data-table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            <th>Registration Number</th>
            <th>Object Name</th>
            <th>Country of Origin</th>
            <th>Date of Launch</th>
            <th>Status</th>
            <th>Orbital Band</th>
            <th>Congestion Risk</th>
            <th className="cell-number">Apogee (km)</th>
            <th className="cell-number">Perigee (km)</th>
            <th className="cell-number">Inclination (°)</th>
            <th className="cell-number">Period (min)</th>
          </tr>
        </thead>
        <tbody>
          {objects.map((obj) => {
            const classNames = []
            if (selectedObject?.['Registration Number'] === obj['Registration Number']) {
              classNames.push('selected')
            }
            if (obj['Status'] === SATELLITE_STATUS.DECAYED || obj['Status'] === SATELLITE_STATUS.DEORBITED) {
              classNames.push('decayed')
            }
            return (
            <tr 
              key={obj['Registration Number']}
              className={classNames.join(' ')}
              onClick={() => onRowClick(obj)}
            >
              <td className="cell-reg">{obj['Registration Number']}</td>
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

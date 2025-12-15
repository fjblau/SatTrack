import './DataTable.css'

export default function DataTable({ objects, selectedObject, onRowClick, loading }) {
  if (loading) {
    return <div className="loading">Loading...</div>
  }

  if (objects.length === 0) {
    return <div className="empty-state">No objects found. Try adjusting your filters.</div>
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
            <th>Apogee (km)</th>
            <th>Perigee (km)</th>
            <th>Inclination (°)</th>
            <th>Period (min)</th>
          </tr>
        </thead>
        <tbody>
          {objects.map((obj) => (
            <tr 
              key={obj['Registration Number']}
              className={selectedObject?.['Registration Number'] === obj['Registration Number'] ? 'selected' : ''}
              onClick={() => onRowClick(obj)}
            >
              <td className="cell-reg">{obj['Registration Number']}</td>
              <td className="cell-name">{obj['Object Name'] || '—'}</td>
              <td>{obj['Country of Origin'] || '—'}</td>
              <td>{obj['Date of Launch'] || '—'}</td>
              <td>{obj['Status'] || '—'}</td>
              <td className="cell-number">{obj['Apogee (km)'] ? obj['Apogee (km)'].toFixed(2) : '—'}</td>
              <td className="cell-number">{obj['Perigee (km)'] ? obj['Perigee (km)'].toFixed(2) : '—'}</td>
              <td className="cell-number">{obj['Inclination (degrees)'] ? obj['Inclination (degrees)'].toFixed(2) : '—'}</td>
              <td className="cell-number">{obj['Period (minutes)'] ? obj['Period (minutes)'].toFixed(2) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

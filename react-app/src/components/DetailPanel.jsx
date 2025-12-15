import './DetailPanel.css'

export default function DetailPanel({ object }) {
  if (!object) {
    return (
      <div className="detail-panel empty">
        <p>Select a row to view detailed information</p>
      </div>
    )
  }

  const formatValue = (value) => {
    if (value === null || value === undefined || value === '') return '—'
    if (typeof value === 'number') return value.toFixed(2)
    return String(value)
  }

  return (
    <div className="detail-panel">
      <div className="detail-header">
        <h2>{object['Object Name'] || object['Registration Number']}</h2>
        <p className="detail-reg">{object['Registration Number']}</p>
      </div>

      <div className="detail-grid">
        <div className="detail-section">
          <h3>Registration & Identification</h3>
          <div className="detail-row">
            <span className="detail-label">International Designator</span>
            <span className="detail-value">{formatValue(object['International Designator'])}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Country of Origin</span>
            <span className="detail-value">{formatValue(object['Country of Origin'])}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">UN Registered</span>
            <span className="detail-value">{object['UN Registered'] === 'T' ? 'Yes' : 'No'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Status</span>
            <span className="detail-value">{formatValue(object['Status'])}</span>
          </div>
        </div>

        <div className="detail-section">
          <h3>Launch Information</h3>
          <div className="detail-row">
            <span className="detail-label">Date of Launch</span>
            <span className="detail-value">{formatValue(object['Date of Launch'])}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Function</span>
            <span className="detail-value">{formatValue(object['Function'])}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Launch Vehicle</span>
            <span className="detail-value">{formatValue(object['Launch Vehicle'])}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Place of Launch</span>
            <span className="detail-value">{formatValue(object['Place of Launch'])}</span>
          </div>
        </div>

        <div className="detail-section">
          <h3>Orbital Parameters</h3>
          <div className="detail-row">
            <span className="detail-label">Apogee</span>
            <span className="detail-value">
              {object['Apogee (km)'] ? `${formatValue(object['Apogee (km)'])} km` : '—'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Perigee</span>
            <span className="detail-value">
              {object['Perigee (km)'] ? `${formatValue(object['Perigee (km)'])} km` : '—'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Inclination</span>
            <span className="detail-value">
              {object['Inclination (degrees)'] ? `${formatValue(object['Inclination (degrees)'])}°` : '—'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Period</span>
            <span className="detail-value">
              {object['Period (minutes)'] ? `${formatValue(object['Period (minutes)'])} minutes` : '—'}
            </span>
          </div>
        </div>

        {object['GSO Location'] && (
          <div className="detail-section">
            <h3>Geostationary</h3>
            <div className="detail-row">
              <span className="detail-label">GSO Location</span>
              <span className="detail-value">{formatValue(object['GSO Location'])}</span>
            </div>
          </div>
        )}

        {object['Secretariat Remarks'] && (
          <div className="detail-section">
            <h3>Remarks</h3>
            <p className="detail-remarks">{object['Secretariat Remarks']}</p>
          </div>
        )}

        {object['Registration Document'] && object['Registration Document'] !== '' && (
          <div className="detail-section">
            <h3>Documentation</h3>
            <a 
              href={`https://www.unoosa.org${object['Registration Document']}`}
              target="_blank"
              rel="noopener noreferrer"
              className="detail-link"
            >
              View Registration Document
            </a>
          </div>
        )}
      </div>
    </div>
  )
}

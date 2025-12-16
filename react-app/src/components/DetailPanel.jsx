import { useState, useEffect } from 'react'
import './DetailPanel.css'
import DataRecordModal from './DataRecordModal'

export default function DetailPanel({ object }) {
  const [orbitalState, setOrbitalState] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [docLink, setDocLink] = useState(null)
  const [docLoading, setDocLoading] = useState(false)
  const [docMetadata, setDocMetadata] = useState(null)
  const [metadataLoading, setMetadataLoading] = useState(false)
  const [showDataRecord, setShowDataRecord] = useState(false)
  const [fullDocument, setFullDocument] = useState(null)

  useEffect(() => {
    if (!object) {
      setOrbitalState(null)
      setError(null)
      setDocLink(null)
      setDocLoading(false)
      setDocMetadata(null)
      setMetadataLoading(false)
      setShowDataRecord(false)
      setFullDocument(null)
      return
    }

    setDocMetadata(null)
    setMetadataLoading(false)

    if (object['Registration Document']) {
      const fetchDocLink = async () => {
        setDocLoading(true)
        try {
          const response = await fetch(
            `/api/documents/resolve?path=${encodeURIComponent(object['Registration Document'])}`
          )
          if (response.ok) {
            const data = await response.json()
            setDocLink(data.english_link || null)
          } else {
            setDocLink(null)
          }
        } catch {
          setDocLink(null)
        } finally {
          setDocLoading(false)
        }
      }
      fetchDocLink()
    } else {
      setDocLink(null)
      setDocLoading(false)
    }

    const fetchSatelliteData = async () => {
      setLoading(true)
      setError(null)
      try {
        const identifier = object._mongodb_id || object['International Designator']
        const response = await fetch(`/v2/satellite/${encodeURIComponent(identifier)}`)
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        const data = await response.json()
        
        if (data.data) {
          setFullDocument(data.data)
          
          const canonical = data.data.canonical || {}
          const orbit = canonical.orbit || {}
          
          setOrbitalState({
            orbital_state: orbit,
            norad_id: canonical.norad_cat_id,
            n2yo_url: canonical.norad_cat_id ? `https://www.n2yo.com/satellite/?s=${canonical.norad_cat_id}` : null,
            tracking_available: !!canonical.norad_cat_id
          })
        }
      } catch (err) {
        console.error('Satellite data fetch error:', err)
        setError(`Error fetching satellite data: ${err.message}`)
      } finally {
        setLoading(false)
      }
    }

    fetchSatelliteData()
  }, [object])

  useEffect(() => {
    if (docLink) {
      const fetchMetadata = async () => {
        setMetadataLoading(true)
        try {
          const response = await fetch(
            `/api/documents/metadata?url=${encodeURIComponent(docLink)}`
          )
          if (response.ok) {
            const data = await response.json()
            setDocMetadata(data)
          }
        } catch (err) {
          console.error('Document metadata fetch error:', err)
        } finally {
          setMetadataLoading(false)
        }
      }
      fetchMetadata()
    }
  }, [docLink])

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

  const ensureProtocol = (url) => {
    if (!url) return url
    if (url.startsWith('http://') || url.startsWith('https://')) return url
    return 'https://' + url
  }

  return (
    <div className="detail-panel">
      <div className="detail-header">
        <h2>{object['Object Name'] || object['Registration Number']}</h2>
        <p className="detail-reg">{object['Registration Number']}</p>
        {fullDocument && (
          <button 
            className="show-data-record-button"
            onClick={() => setShowDataRecord(true)}
          >
            Show Data Record
          </button>
        )}
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
          {loading && <p className="detail-loading">Loading orbital data...</p>}
          {orbitalState && orbitalState.orbital_state && (
            <div className="orbital-data">
              <div className="detail-row">
                <span className="detail-label">Data Source</span>
                <span className="detail-value">{orbitalState.orbital_state.data_source}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Apogee</span>
                <span className="detail-value">{formatValue(orbitalState.orbital_state.apogee_km)} km</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Perigee</span>
                <span className="detail-value">{formatValue(orbitalState.orbital_state.perigee_km)} km</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Inclination</span>
                <span className="detail-value">{formatValue(orbitalState.orbital_state.inclination_degrees)}°</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Period</span>
                <span className="detail-value">{formatValue(orbitalState.orbital_state.period_minutes)} minutes</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Semi-major Axis</span>
                <span className="detail-value">{formatValue(orbitalState.orbital_state.semi_major_axis_km)} km</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Eccentricity</span>
                <span className="detail-value">{formatValue(orbitalState.orbital_state.eccentricity)}</span>
              </div>
            </div>
          )}
          {!loading && !orbitalState?.orbital_state && (
            <>
              {(object['Apogee (km)'] || docMetadata?.metadata?.apogee_km) && (
                <div className="detail-row">
                  <span className="detail-label">Data Source</span>
                  <span className="detail-value">
                    {docMetadata?.metadata?.apogee_km && !object['Apogee (km)'] ? 'From registration document' : 'Static registry'}
                  </span>
                </div>
              )}
              <div className="detail-row">
                <span className="detail-label">Apogee</span>
                <span className="detail-value">
                  {object['Apogee (km)'] ? `${formatValue(object['Apogee (km)'])} km` : (docMetadata?.metadata?.apogee_km ? `${formatValue(docMetadata.metadata.apogee_km)} km` : '—')}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Perigee</span>
                <span className="detail-value">
                  {object['Perigee (km)'] ? `${formatValue(object['Perigee (km)'])} km` : (docMetadata?.metadata?.perigee_km ? `${formatValue(docMetadata.metadata.perigee_km)} km` : '—')}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Inclination</span>
                <span className="detail-value">
                  {object['Inclination (degrees)'] ? `${formatValue(object['Inclination (degrees)'])}°` : (docMetadata?.metadata?.inclination_degrees ? `${formatValue(docMetadata.metadata.inclination_degrees)}°` : '—')}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Period</span>
                <span className="detail-value">
                  {object['Period (minutes)'] ? `${formatValue(object['Period (minutes)'])} minutes` : (docMetadata?.metadata?.nodal_period_minutes ? `${formatValue(docMetadata.metadata.nodal_period_minutes)} minutes` : '—')}
                </span>
              </div>
            </>
          )}
          {error && <p className="detail-error">{error}</p>}
        </div>

        {orbitalState?.n2yo_url && (
          <div className="detail-section">
            <h3>Live Tracking</h3>
            <a 
              href={orbitalState.n2yo_url}
              target="_blank"
              rel="noopener noreferrer"
              className="detail-link"
            >
              Track on N2YO (NORAD {orbitalState.norad_id})
            </a>
          </div>
        )}

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
            {docLoading && <p className="detail-loading">Finding document...</p>}
            {!docLoading && docLink && (
              <>
                <a 
                  href={docLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="detail-link"
                >
                  View Registration Document (PDF)
                </a>
                {metadataLoading && <p className="detail-loading">Extracting document information...</p>}
                {docMetadata && docMetadata.metadata && (
                  <div className="document-metadata">
                    {docMetadata.metadata.owner_operator && (
                      <div className="detail-row">
                        <span className="detail-label">Owner/Operator</span>
                        <span className="detail-value">{docMetadata.metadata.owner_operator}</span>
                      </div>
                    )}
                    {docMetadata.metadata.website && (
                      <div className="detail-row">
                        <span className="detail-label">Website</span>
                        <a 
                          href={ensureProtocol(docMetadata.metadata.website)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="detail-link-inline"
                        >
                          {docMetadata.metadata.website}
                        </a>
                      </div>
                    )}
                    {docMetadata.metadata.launch_vehicle && (
                      <div className="detail-row">
                        <span className="detail-label">Launch Vehicle (from document)</span>
                        <span className="detail-value">{docMetadata.metadata.launch_vehicle}</span>
                      </div>
                    )}
                    {docMetadata.metadata.place_of_launch && (
                      <div className="detail-row">
                        <span className="detail-label">Place of Launch (from document)</span>
                        <span className="detail-value">{docMetadata.metadata.place_of_launch}</span>
                      </div>
                    )}
                    {(docMetadata.metadata.apogee_km || docMetadata.metadata.perigee_km || docMetadata.metadata.inclination_degrees || docMetadata.metadata.nodal_period_minutes) && (orbitalState?.orbital_state || object['Apogee (km)']) && (
                      <div className="document-orbital-params">
                        <h4>Orbital Parameters (from document)</h4>
                        {docMetadata.metadata.apogee_km && (
                          <div className="detail-row">
                            <span className="detail-label">Apogee</span>
                            <span className="detail-value">{docMetadata.metadata.apogee_km} km</span>
                          </div>
                        )}
                        {docMetadata.metadata.perigee_km && (
                          <div className="detail-row">
                            <span className="detail-label">Perigee</span>
                            <span className="detail-value">{docMetadata.metadata.perigee_km} km</span>
                          </div>
                        )}
                        {docMetadata.metadata.inclination_degrees && (
                          <div className="detail-row">
                            <span className="detail-label">Inclination</span>
                            <span className="detail-value">{docMetadata.metadata.inclination_degrees}°</span>
                          </div>
                        )}
                        {docMetadata.metadata.nodal_period_minutes && (
                          <div className="detail-row">
                            <span className="detail-label">Nodal Period</span>
                            <span className="detail-value">{docMetadata.metadata.nodal_period_minutes} minutes</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
            {!docLoading && !docLink && (
              <p className="detail-error">Document not found</p>
            )}
          </div>
        )}
      </div>

      {showDataRecord && (
        <DataRecordModal 
          data={fullDocument}
          onClose={() => setShowDataRecord(false)}
        />
      )}
    </div>
  )
}

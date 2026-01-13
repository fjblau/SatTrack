import { useState, useEffect } from 'react'
import GraphViewer from './GraphViewer'
import './GraphExplorer.css'

function GraphExplorer() {
  const [graphType, setGraphType] = useState('constellation')
  const [constellations, setConstellations] = useState([])
  const [documents, setDocuments] = useState([])
  const [orbitalBands, setOrbitalBands] = useState([])
  const [launchYears, setLaunchYears] = useState([])
  const [selectedConstellation, setSelectedConstellation] = useState('')
  const [selectedDocument, setSelectedDocument] = useState('')
  const [selectedOrbitalBand, setSelectedOrbitalBand] = useState('')
  const [selectedTimePeriod, setSelectedTimePeriod] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadGraphStats()
  }, [])

  const loadGraphStats = async () => {
    setLoading(true)
    try {
      const response = await fetch('/v2/graphs/stats')
      const data = await response.json()
      
      if (data.data) {
        const filteredConstellations = (data.data.constellations || []).filter(c => c.name !== 'Other')
        setConstellations(filteredConstellations)
        setDocuments(data.data.top_registration_documents || [])
        setOrbitalBands(data.data.proximity_by_orbital_band || [])
        setLaunchYears(data.data.recent_launch_years || [])
        
        if (filteredConstellations.length > 0) {
          setSelectedConstellation(filteredConstellations[0].name)
        }
        if (data.data.top_registration_documents && data.data.top_registration_documents.length > 0) {
          setSelectedDocument(data.data.top_registration_documents[0].key)
        }
        if (data.data.proximity_by_orbital_band && data.data.proximity_by_orbital_band.length > 0) {
          setSelectedOrbitalBand(data.data.proximity_by_orbital_band[0].orbital_band)
        }
        if (data.data.recent_launch_years && data.data.recent_launch_years.length > 0) {
          setSelectedTimePeriod(data.data.recent_launch_years[0].year.toString())
        }
      }
    } catch (error) {
      console.error('Error loading graph stats:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="graph-explorer">
      <div className="graph-sidebar">
        <div className="graph-type-selector">
          <button 
            className={graphType === 'constellation' ? 'active' : ''}
            onClick={() => setGraphType('constellation')}
          >
            Constellations
          </button>
          <button 
            className={graphType === 'registration' ? 'active' : ''}
            onClick={() => setGraphType('registration')}
          >
            Registration Docs
          </button>
          <button 
            className={graphType === 'proximity' ? 'active' : ''}
            onClick={() => setGraphType('proximity')}
          >
            Orbital Proximity
          </button>
          <button 
            className={graphType === 'timeline' ? 'active' : ''}
            onClick={() => setGraphType('timeline')}
          >
            Launch Timeline
          </button>
        </div>

        {graphType === 'constellation' && (
          <div className="selector-content">
            <h3>Constellations</h3>
            {loading ? (
              <p>Loading...</p>
            ) : (
              <div className="item-list">
                {constellations.map((constellation) => (
                  <div
                    key={constellation.name}
                    className={`list-item ${selectedConstellation === constellation.name ? 'selected' : ''}`}
                    onClick={() => setSelectedConstellation(constellation.name)}
                  >
                    <div className="item-name">{constellation.name}</div>
                    <div className="item-count">{constellation.member_count.toLocaleString()} satellites</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {graphType === 'registration' && (
          <div className="selector-content">
            <h3>Top Registration Documents</h3>
            {loading ? (
              <p>Loading...</p>
            ) : (
              <div className="item-list">
                {documents.map((doc) => (
                  <div
                    key={doc.key}
                    className={`list-item ${selectedDocument === doc.key ? 'selected' : ''}`}
                    onClick={() => setSelectedDocument(doc.key)}
                  >
                    <div className="item-name">{doc.url}</div>
                    <div className="item-count">{doc.satellite_count} satellites</div>
                    <div className="item-meta">{doc.countries.join(', ')}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {graphType === 'proximity' && (
          <div className="selector-content">
            <h3>Orbital Proximity</h3>
            <p className="section-description">Satellites with similar orbits (within ±50km apogee/perigee, ±5° inclination)</p>
            {loading ? (
              <p>Loading...</p>
            ) : (
              <div className="item-list">
                {orbitalBands.map((band) => (
                  <div
                    key={band.orbital_band}
                    className={`list-item ${selectedOrbitalBand === band.orbital_band ? 'selected' : ''}`}
                    onClick={() => setSelectedOrbitalBand(band.orbital_band)}
                  >
                    <div className="item-name">{band.orbital_band}</div>
                    <div className="item-count">{band.edge_count.toLocaleString()} proximity edges</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {graphType === 'timeline' && (
          <div className="selector-content">
            <h3>Launch Timeline</h3>
            <p className="section-description">Satellites grouped by launch year (98.6% coverage)</p>
            {loading ? (
              <p>Loading...</p>
            ) : (
              <div className="item-list">
                {launchYears.map((yearData) => (
                  <div
                    key={yearData.year}
                    className={`list-item ${selectedTimePeriod === yearData.year.toString() ? 'selected' : ''}`}
                    onClick={() => setSelectedTimePeriod(yearData.year.toString())}
                  >
                    <div className="item-name">{yearData.year}</div>
                    <div className="item-count">{yearData.satellite_count.toLocaleString()} satellites</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="graph-main">
        <GraphViewer 
          graphType={graphType}
          selectedConstellation={graphType === 'constellation' ? selectedConstellation : null}
          selectedDocument={graphType === 'registration' ? selectedDocument : null}
          selectedOrbitalBand={graphType === 'proximity' ? selectedOrbitalBand : null}
          selectedTimePeriod={graphType === 'timeline' ? selectedTimePeriod : null}
        />
      </div>
    </div>
  )
}

export default GraphExplorer

import { useState, useEffect } from 'react'
import GraphViewer from './GraphViewer'
import PathFinderPanel from './PathFinderPanel'
import CentralityView from './CentralityView'
import CollisionRiskView from './CollisionRiskView'
import EvolutionTimelineView from './EvolutionTimelineView'
import './GraphExplorer.css'
import { API_ENDPOINTS, GRAPH_SETTINGS, UI_TEXT } from '../config/constants'

function GraphExplorer() {
  const [graphType, setGraphType] = useState('constellation')
  const [constellations, setConstellations] = useState([])
  const [documents, setDocuments] = useState([])
  const [orbitalBands, setOrbitalBands] = useState([])
  const [functionCategories, setFunctionCategories] = useState([])
  const [countries, setCountries] = useState([])
  const [selectedConstellation, setSelectedConstellation] = useState('')
  const [selectedDocument, setSelectedDocument] = useState('')
  const [selectedOrbitalBand, setSelectedOrbitalBand] = useState('')
  const [selectedFunctionCategories, setSelectedFunctionCategories] = useState([])
  const [selectedCountries, setSelectedCountries] = useState([])
  const [loading, setLoading] = useState(false)
  const [pathData, setPathData] = useState(null)
  const [centralityData, setCentralityData] = useState(null)
  const [centralityMetric, setCentralityMetric] = useState(null)
  const [collisionRiskData, setCollisionRiskData] = useState(null)
  const [collisionViewType, setCollisionViewType] = useState(null)
  const [evolutionTimelineData, setEvolutionTimelineData] = useState(null)
  const [selectedSatellite, setSelectedSatellite] = useState(null)
  const [satelliteSearchQuery, setSatelliteSearchQuery] = useState('')
  const [satelliteSearchResults, setSatelliteSearchResults] = useState([])
  const [searchingsatellite, setSearchingsatellite] = useState(false)

  useEffect(() => {
    loadGraphStats()
    loadFunctionCategories()
    loadCountryRelations()
  }, [])

  const loadGraphStats = async () => {
    setLoading(true)
    try {
      const response = await fetch(API_ENDPOINTS.GRAPHS.STATS)
      const data = await response.json()
      
      if (data.data) {
        const filteredConstellations = (data.data.constellations || []).filter(c => !GRAPH_SETTINGS.EXCLUDED_CONSTELLATIONS.includes(c.name))
        setConstellations(filteredConstellations)
        setDocuments(data.data.top_registration_documents || [])
        setOrbitalBands(data.data.proximity_by_orbital_band || [])
        
        if (filteredConstellations.length > 0) {
          setSelectedConstellation(filteredConstellations[0].name)
        }
        if (data.data.top_registration_documents && data.data.top_registration_documents.length > 0) {
          setSelectedDocument(data.data.top_registration_documents[0].key)
        }
        if (data.data.proximity_by_orbital_band && data.data.proximity_by_orbital_band.length > 0) {
          setSelectedOrbitalBand(data.data.proximity_by_orbital_band[0].orbital_band)
        }
      }
    } catch (error) {
      console.error('Error loading graph stats:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadFunctionCategories = async () => {
    try {
      const response = await fetch(`${API_ENDPOINTS.GRAPHS.FUNCTION_SIMILARITY}?limit=${GRAPH_SETTINGS.FUNCTION_SIMILARITY_LIMIT}`)
      const data = await response.json()
      
      if (data.data && data.data.categories) {
        setFunctionCategories(data.data.categories)
      }
    } catch (error) {
      console.error('Error loading function categories:', error)
    }
  }

  const handleFunctionCategoryClick = (category) => {
    setSelectedFunctionCategories(prev => {
      if (prev.includes(category)) {
        return prev.filter(c => c !== category)
      } else {
        return [...prev, category]
      }
    })
  }

  const loadCountryRelations = async () => {
    try {
      const response = await fetch(`${API_ENDPOINTS.GRAPHS.COUNTRY_RELATIONS}?min_satellites=${GRAPH_SETTINGS.COUNTRY_RELATIONS_MIN_SATELLITES}&limit_countries=${GRAPH_SETTINGS.COUNTRY_RELATIONS_LIMIT}`)
      const data = await response.json()
      
      if (data.data && data.data.nodes) {
        setCountries(data.data.nodes)
      }
    } catch (error) {
      console.error('Error loading country relations:', error)
    }
  }

  const handleCountryClick = (country) => {
    setSelectedCountries(prev => {
      if (prev.includes(country)) {
        return prev.filter(c => c !== country)
      } else {
        return [...prev, country]
      }
    })
  }

  const searchSatellites = async (query) => {
    if (!query || query.length < 2) {
      setSatelliteSearchResults([])
      return
    }
    
    setSearchingsatellite(true)
    try {
      const response = await fetch(`${API_ENDPOINTS.SEARCH}?q=${encodeURIComponent(query)}&limit=10`)
      const data = await response.json()
      
      if (data.data) {
        const results = data.data.map(item => ({
          id: item._id,
          name: item.canonical?.object_name || item.canonical?.name || item.canonical?.registration_number || item._id,
          registration: item.canonical?.registration_number || ''
        }))
        setSatelliteSearchResults(results)
      }
    } catch (error) {
      console.error('Error searching satellites:', error)
      setSatelliteSearchResults([])
    } finally {
      setSearchingsatellite(false)
    }
  }

  const handleSatelliteSelect = (satellite) => {
    setSelectedSatellite(satellite.id)
    setSatelliteSearchQuery(satellite.name)
    setSatelliteSearchResults([])
  }

  const handleSearchInputChange = (value) => {
    setSatelliteSearchQuery(value)
    if (value.length >= 2) {
      searchSatellites(value)
    } else {
      setSatelliteSearchResults([])
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
            className={graphType === 'function' ? 'active' : ''}
            onClick={() => setGraphType('function')}
          >
            Function Similarity
          </button>
          <button 
            className={graphType === 'country' ? 'active' : ''}
            onClick={() => setGraphType('country')}
          >
            Country Relations
          </button>
          <button 
            className={graphType === 'paths' ? 'active' : ''}
            onClick={() => setGraphType('paths')}
          >
            Path Finder
          </button>
          <button 
            className={graphType === 'centrality' ? 'active' : ''}
            onClick={() => setGraphType('centrality')}
          >
            Centrality Analysis
          </button>
          <button 
            className={graphType === 'collision' ? 'active' : ''}
            onClick={() => setGraphType('collision')}
          >
            Collision Risks
          </button>
          <button 
            className={graphType === 'lineage' ? 'active' : ''}
            onClick={() => setGraphType('lineage')}
          >
            Satellite Lineage
          </button>
          <button 
            className={graphType === 'communities' ? 'active' : ''}
            onClick={() => setGraphType('communities')}
          >
            Communities
          </button>
          <button 
            className={graphType === 'evolution' ? 'active' : ''}
            onClick={() => setGraphType('evolution')}
          >
            Graph Evolution
          </button>
        </div>

        {graphType === 'constellation' && (
          <div className="selector-content">
            <h3>Constellations</h3>
            {loading ? (
              <p>{UI_TEXT.LOADING}</p>
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
              <p>{UI_TEXT.LOADING}</p>
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
            <p className="section-description">{UI_TEXT.PROXIMITY_DESCRIPTION}</p>
            {loading ? (
              <p>{UI_TEXT.LOADING}</p>
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

        {graphType === 'function' && (
          <div className="selector-content">
            <h3>Function Categories</h3>
            <p className="section-description">{UI_TEXT.SELECT_MULTIPLE_CATEGORIES}</p>
            {loading ? (
              <p>{UI_TEXT.LOADING}</p>
            ) : (
              <div className="item-list">
                {functionCategories.map((category) => (
                  <div
                    key={category.category}
                    className={`list-item ${selectedFunctionCategories.includes(category.category) ? 'selected' : ''}`}
                    onClick={() => handleFunctionCategoryClick(category.category)}
                  >
                    <div className="item-name">{category.category}</div>
                    <div className="item-count">{category.satellite_count.toLocaleString()} satellites</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {graphType === 'country' && (
          <div className="selector-content">
            <h3>Country Relations</h3>
            <p className="section-description">{UI_TEXT.SHIFT_SELECT_COUNTRIES}</p>
            {loading ? (
              <p>{UI_TEXT.LOADING}</p>
            ) : (
              <div className="item-list">
                {countries.map((country) => (
                  <div
                    key={country.country}
                    className={`list-item ${selectedCountries.includes(country.country) ? 'selected' : ''}`}
                    onClick={() => handleCountryClick(country.country)}
                  >
                    <div className="item-name">{country.country}</div>
                    <div className="item-count">{country.satellite_count.toLocaleString()} satellites</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {graphType === 'paths' && (
          <div className="selector-content">
            <PathFinderPanel onPathSelect={(data) => setPathData(data)} />
          </div>
        )}

        {graphType === 'centrality' && (
          <div className="selector-content">
            <CentralityView onCentralitySelect={(data, metric) => {
              setCentralityData(data)
              setCentralityMetric(metric)
            }} />
          </div>
        )}

        {graphType === 'collision' && (
          <div className="selector-content">
            <CollisionRiskView onCollisionRiskSelect={(data, viewType) => {
              setCollisionRiskData(data)
              setCollisionViewType(viewType)
            }} />
          </div>
        )}

        {graphType === 'lineage' && (
          <div className="selector-content">
            <h3>Satellite Lineage</h3>
            <p className="section-description">Explore satellite family relationships and generations</p>
            
            <div style={{ marginTop: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                Search Satellite:
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  value={satelliteSearchQuery}
                  onChange={(e) => handleSearchInputChange(e.target.value)}
                  placeholder="Enter satellite name or registration..."
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                    fontSize: '0.9rem'
                  }}
                />
                {searchingsatellite && (
                  <div style={{ 
                    position: 'absolute', 
                    right: '0.5rem', 
                    top: '50%', 
                    transform: 'translateY(-50%)',
                    fontSize: '0.8rem',
                    color: '#666'
                  }}>
                    Searching...
                  </div>
                )}
                {satelliteSearchResults.length > 0 && (
                  <div style={{
                    position: 'absolute',
                    top: '100%',
                    left: 0,
                    right: 0,
                    maxHeight: '300px',
                    overflowY: 'auto',
                    backgroundColor: 'white',
                    border: '1px solid #ddd',
                    borderTop: 'none',
                    borderRadius: '0 0 4px 4px',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                    zIndex: 1000
                  }}>
                    {satelliteSearchResults.map((satellite) => (
                      <div
                        key={satellite.id}
                        onClick={() => handleSatelliteSelect(satellite)}
                        style={{
                          padding: '0.75rem',
                          cursor: 'pointer',
                          borderBottom: '1px solid #f0f0f0',
                          transition: 'background-color 0.2s'
                        }}
                        onMouseEnter={(e) => e.target.style.backgroundColor = '#f5f5f5'}
                        onMouseLeave={(e) => e.target.style.backgroundColor = 'white'}
                      >
                        <div style={{ fontWeight: '500', fontSize: '0.9rem' }}>
                          {satellite.name}
                        </div>
                        {satellite.registration && (
                          <div style={{ fontSize: '0.8rem', color: '#666', marginTop: '0.25rem' }}>
                            {satellite.registration}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            
            {selectedSatellite && (
              <div style={{
                marginTop: '1rem',
                padding: '0.75rem',
                backgroundColor: '#e8f5e9',
                border: '1px solid #4caf50',
                borderRadius: '4px'
              }}>
                <div style={{ fontSize: '0.85rem', color: '#2e7d32', fontWeight: '500' }}>
                  ✓ Selected: {satelliteSearchQuery}
                </div>
                <button
                  onClick={() => {
                    setSelectedSatellite(null)
                    setSatelliteSearchQuery('')
                  }}
                  style={{
                    marginTop: '0.5rem',
                    padding: '0.25rem 0.75rem',
                    fontSize: '0.8rem',
                    backgroundColor: 'white',
                    border: '1px solid #4caf50',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    color: '#2e7d32'
                  }}
                >
                  Clear Selection
                </button>
              </div>
            )}
          </div>
        )}

        {graphType === 'communities' && (
          <div className="selector-content">
            <h3>Community Detection</h3>
            <p className="section-description">Discover clusters and communities in the satellite network</p>
            <p style={{ fontSize: '0.85rem', color: '#6c757d', marginTop: '1rem' }}>
              Communities will be automatically detected and visualized.
            </p>
          </div>
        )}

        {graphType === 'evolution' && (
          <div className="selector-content">
            <h3>Graph Evolution Timeline</h3>
            <p className="section-description">Visualize how the satellite network has grown over time</p>
            <p style={{ fontSize: '0.85rem', color: '#6c757d', marginTop: '1rem' }}>
              Track node count, edge count, density, and growth metrics across different time periods.
            </p>
          </div>
        )}

      </div>

      <div className="graph-main">
        {graphType === 'evolution' ? (
          <EvolutionTimelineView onTimelineLoad={(data) => setEvolutionTimelineData(data)} />
        ) : (
          <GraphViewer 
            graphType={graphType}
            selectedConstellation={graphType === 'constellation' ? selectedConstellation : null}
            selectedDocument={graphType === 'registration' ? selectedDocument : null}
            selectedOrbitalBand={graphType === 'proximity' ? selectedOrbitalBand : null}
            selectedFunctionCategories={graphType === 'function' ? selectedFunctionCategories : null}
            selectedCountries={graphType === 'country' ? selectedCountries : null}
            pathData={graphType === 'paths' ? pathData : null}
            centralityData={graphType === 'centrality' ? centralityData : null}
            centralityMetric={graphType === 'centrality' ? centralityMetric : null}
            collisionRiskData={graphType === 'collision' ? collisionRiskData : null}
            collisionViewType={graphType === 'collision' ? collisionViewType : null}
            selectedSatellite={graphType === 'lineage' ? selectedSatellite : null}
          />
        )}
      </div>
    </div>
  )
}

export default GraphExplorer

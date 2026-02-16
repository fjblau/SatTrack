import { useState, useEffect } from 'react'
import GraphViewer from './GraphViewer'
import PathFinderPanel from './PathFinderPanel'
import CollisionRiskView from './CollisionRiskView'
import ConstellationBrowser from './ConstellationBrowser'
import SatelliteNeighborhood from './SatelliteNeighborhood'
import FunctionAnalytics from './FunctionAnalytics'
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
  const [selectedOrbitalBands, setSelectedOrbitalBands] = useState([])
  const [selectedCountries, setSelectedCountries] = useState([])
  const [functionClusters, setFunctionClusters] = useState([])
  const [availableOrbitalBands, setAvailableOrbitalBands] = useState([])
  const [loading, setLoading] = useState(false)
  const [pathData, setPathData] = useState(null)
  const [collisionRiskData, setCollisionRiskData] = useState(null)
  const [collisionViewType, setCollisionViewType] = useState(null)
  const [selectedSatellite, setSelectedSatellite] = useState(null)
  const [satelliteSearchQuery, setSatelliteSearchQuery] = useState('')
  const [satelliteSearchResults, setSatelliteSearchResults] = useState([])
  const [searchingsatellite, setSearchingsatellite] = useState(false)
  const [constellationBrowserData, setConstellationBrowserData] = useState(null)
  const [neighborhoodData, setNeighborhoodData] = useState(null)

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
      const response = await fetch(`${API_ENDPOINTS.GRAPHS.FUNCTION_SIMILARITY}?top_n=15`)
      const data = await response.json()
      
      if (data.data && data.data.clusters) {
        setFunctionClusters(data.data.clusters)
        
        const uniqueFunctions = [...new Set(data.data.clusters.map(c => c.function))]
        const functionCategoriesData = uniqueFunctions.map(func => ({
          category: func,
          satellite_count: data.data.clusters
            .filter(c => c.function === func)
            .reduce((sum, c) => sum + c.satellite_count, 0)
        }))
        setFunctionCategories(functionCategoriesData)
        
        // Auto-select first function category on load
        if (functionCategoriesData.length > 0 && selectedFunctionCategories.length === 0) {
          setSelectedFunctionCategories([functionCategoriesData[0].category])
        }
        
        const uniqueBands = [...new Set(data.data.clusters.map(c => c.orbital_band))]
        setAvailableOrbitalBands(uniqueBands)
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

  const handleOrbitalBandClick = (band) => {
    setSelectedOrbitalBands(prev => {
      if (prev.includes(band)) {
        return prev.filter(b => b !== band)
      } else {
        return [...prev, band]
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
            className={graphType === 'constellation-browser' ? 'active' : ''}
            onClick={() => setGraphType('constellation-browser')}
          >
            Constellation Browser
          </button>
          <button 
            className={graphType === 'neighborhood' ? 'active' : ''}
            onClick={() => setGraphType('neighborhood')}
          >
            Satellite Neighborhood
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
            className={graphType === 'analytics' ? 'active' : ''}
            onClick={() => setGraphType('analytics')}
            style={{ borderLeft: '2px solid #ddd', marginLeft: '0.5rem', paddingLeft: '0.75rem' }}
          >
            📊 Analytics
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
            {(selectedFunctionCategories.length > 0 || selectedOrbitalBands.length > 0) && (
              <div style={{ 
                background: '#e3f2fd', 
                border: '1px solid #2196f3', 
                borderRadius: '4px', 
                padding: '0.75rem', 
                marginBottom: '1rem',
                fontSize: '0.9em'
              }}>
                <div style={{ fontWeight: '600', marginBottom: '0.5rem', color: '#1976d2' }}>
                  Active Filters:
                </div>
                {selectedFunctionCategories.length > 0 && (
                  <div style={{ marginBottom: '0.25rem' }}>
                    <strong>Functions:</strong> {selectedFunctionCategories.join(', ')}
                  </div>
                )}
                {selectedOrbitalBands.length > 0 && (
                  <div style={{ marginBottom: '0.5rem' }}>
                    <strong>Bands:</strong> {selectedOrbitalBands.join(', ')}
                  </div>
                )}
                <button
                  onClick={() => {
                    setSelectedFunctionCategories([])
                    setSelectedOrbitalBands([])
                  }}
                  style={{
                    padding: '0.4rem 0.8rem',
                    background: '#2196f3',
                    color: 'white',
                    border: 'none',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    fontSize: '0.85em',
                    fontWeight: '500'
                  }}
                >
                  Show All Clusters
                </button>
              </div>
            )}
            
            <div style={{ marginBottom: '1rem', padding: '0.75rem', background: '#f5f5f5', borderRadius: '4px' }}>
              <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9em', color: '#666' }}>View Mode</h4>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  style={{
                    flex: 1,
                    padding: '0.5rem',
                    background: '#3498db',
                    color: 'white',
                    border: 'none',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    fontSize: '0.85em',
                    fontWeight: '500'
                  }}
                >
                  Cluster View
                </button>
                <button
                  style={{
                    flex: 1,
                    padding: '0.5rem',
                    background: '#e0e0e0',
                    color: '#666',
                    border: 'none',
                    borderRadius: '3px',
                    cursor: 'not-allowed',
                    fontSize: '0.85em',
                    fontWeight: '500',
                    opacity: 0.6
                  }}
                  disabled
                  title="Double-click a cluster in the graph to view details"
                >
                  Satellite View
                </button>
              </div>
              <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.75em', color: '#888' }}>
                💡 Tip: Double-click a cluster node to drill down into individual satellites
              </p>
            </div>
            
            <h3>Top Clusters</h3>
            <p className="section-description">Showing clusters with highest edge counts</p>
            {loading ? (
              <p>{UI_TEXT.LOADING}</p>
            ) : (
              <>
                <div className="item-list" style={{ marginBottom: '1rem', maxHeight: '200px', overflowY: 'auto' }}>
                  {functionClusters.map((cluster) => (
                    <div
                      key={cluster.cluster_id}
                      className="list-item"
                      style={{ cursor: 'default', padding: '0.75rem', marginBottom: '0.5rem' }}
                    >
                      <div className="item-name" style={{ fontWeight: '600' }}>{cluster.cluster_id}</div>
                      <div className="item-count">{cluster.satellite_count} satellites, {cluster.edge_count} edges</div>
                      <div className="item-meta" style={{ fontSize: '0.85em', color: '#666' }}>
                        Density: {(cluster.density * 100).toFixed(2)}%
                      </div>
                    </div>
                  ))}
                </div>

                <h3 style={{ marginTop: '1.5rem' }}>Filter by Function</h3>
                <div className="item-list" style={{ marginBottom: '1rem' }}>
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

                <h3 style={{ marginTop: '1.5rem' }}>Filter by Orbital Band</h3>
                <div className="item-list">
                  {availableOrbitalBands.map((band) => (
                    <div
                      key={band}
                      className={`list-item ${selectedOrbitalBands.includes(band) ? 'selected' : ''}`}
                      onClick={() => handleOrbitalBandClick(band)}
                    >
                      <div className="item-name">{band}</div>
                    </div>
                  ))}
                </div>
              </>
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

        {graphType === 'constellation-browser' && (
          <div className="selector-content">
            <ConstellationBrowser 
              constellations={constellations}
              onConstellationSelect={(data, name) => {
                setConstellationBrowserData(data)
              }}
            />
          </div>
        )}

        {graphType === 'neighborhood' && (
          <div className="selector-content">
            <SatelliteNeighborhood 
              onNeighborhoodLoad={(data, satellite) => {
                setNeighborhoodData(data)
              }}
            />
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



      </div>

      <div className="graph-main">
        {graphType === 'analytics' ? (
          <FunctionAnalytics />
        ) : (
          <GraphViewer 
            graphType={graphType}
            selectedConstellation={graphType === 'constellation' ? selectedConstellation : null}
            selectedDocument={graphType === 'registration' ? selectedDocument : null}
            selectedOrbitalBand={graphType === 'proximity' ? selectedOrbitalBand : null}
            selectedFunctionCategories={graphType === 'function' ? selectedFunctionCategories : null}
            selectedOrbitalBands={graphType === 'function' ? selectedOrbitalBands : null}
            selectedCountries={graphType === 'country' ? selectedCountries : null}
            pathData={graphType === 'paths' ? pathData : null}
            collisionRiskData={graphType === 'collision' ? collisionRiskData : null}
            collisionViewType={graphType === 'collision' ? collisionViewType : null}
            selectedSatellite={graphType === 'lineage' ? selectedSatellite : null}
            constellationBrowserData={graphType === 'constellation-browser' ? constellationBrowserData : null}
            neighborhoodData={graphType === 'neighborhood' ? neighborhoodData : null}
            functionClusters={graphType === 'function' ? functionClusters : null}
          />
        )}
      </div>
    </div>
  )
}

export default GraphExplorer

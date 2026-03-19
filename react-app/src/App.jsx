import { useState, useEffect } from 'react'
import './App.css'
import DataTable from './components/DataTable'
import DetailPanel from './components/DetailPanel'
import Filters from './components/Filters'
import GraphExplorer from './components/GraphExplorer'
import TimelineChart from './components/TimelineChart'
import FunctionAnalytics from './components/FunctionAnalytics'
import RegistrationDocumentAnalytics from './components/RegistrationDocumentAnalytics'
import AdminPage from './components/AdminPage'
import ObservationsView from './components/ObservationsView'
import LoginPage from './components/LoginPage'
import apiFetch from './utils/apiFetch'
import { API_ENDPOINTS, PAGINATION, ORBITAL_RANGES, UI_TEXT } from './config/constants'

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem('auth_token'))
  const [isDemo, setIsDemo] = useState(() => sessionStorage.getItem('is_demo') === 'true')
  const [activeTab, setActiveTab] = useState('table')
  const [selectedTimePeriod, setSelectedTimePeriod] = useState('')
  const [selectedAnalytics, setSelectedAnalytics] = useState('function-similarity')
  const [launchYears, setLaunchYears] = useState([])
  const [objects, setObjects] = useState([])
  const [filters, setFilters] = useState({})
  const [selectedObject, setSelectedObject] = useState(null)
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [filterOptions, setFilterOptions] = useState({})
  const [sortConfig, setSortConfig] = useState([])

  const limit = PAGINATION.DEFAULT_PAGE_SIZE

  const analyticsPages = [
    {
      id: 'function-similarity',
      name: 'Function Similarity',
      description: 'Satellite function relationships and clustering'
    },
    {
      id: 'registration-docs',
      name: 'Registration Docs',
      description: 'Registration documents analytics and statistics'
    }
  ]

  useEffect(() => {
    const handleAuthExpired = () => {
      sessionStorage.removeItem('auth_token')
      setToken(null)
    }
    window.addEventListener('auth:expired', handleAuthExpired)
    return () => window.removeEventListener('auth:expired', handleAuthExpired)
  }, [])

  useEffect(() => {
    fetchFilterOptions()
    fetchLaunchYears()
  }, [])

  useEffect(() => {
    fetchObjects()
    setPage(0)
  }, [filters])

  useEffect(() => {
    fetchObjects(0)
  }, [sortConfig])

  const fetchFilterOptions = async () => {
    try {
      const [countriesRes, statusesRes, orbitalBandsRes, congestionRisksRes, objectTypesRes] = await Promise.all([
        apiFetch(API_ENDPOINTS.COUNTRIES),
        apiFetch(API_ENDPOINTS.STATUSES),
        apiFetch(API_ENDPOINTS.ORBITAL_BANDS),
        apiFetch(API_ENDPOINTS.CONGESTION_RISKS),
        apiFetch(API_ENDPOINTS.OBJECT_TYPES)
      ])
      const countriesData = await countriesRes.json()
      const statusesData = await statusesRes.json()
      const orbitalBandsData = await orbitalBandsRes.json()
      const congestionRisksData = await congestionRisksRes.json()
      const objectTypesData = await objectTypesRes.json()
      
      setFilterOptions({
        countries: countriesData.countries || [],
        statuses: statusesData.statuses || [],
        orbital_bands: orbitalBandsData.orbital_bands || [],
        congestion_risks: congestionRisksData.congestion_risks || [],
        object_types: objectTypesData.object_types || [],
        apogee_range: [ORBITAL_RANGES.APOGEE.MIN, ORBITAL_RANGES.APOGEE.MAX],
        perigee_range: [ORBITAL_RANGES.PERIGEE.MIN, ORBITAL_RANGES.PERIGEE.MAX],
        inclination_range: [ORBITAL_RANGES.INCLINATION.MIN, ORBITAL_RANGES.INCLINATION.MAX]
      })
    } catch (error) {
      console.error('Error fetching filters:', error)
    }
  }

  const fetchLaunchYears = async () => {
    try {
      const response = await apiFetch(API_ENDPOINTS.GRAPHS.STATS)
      const data = await response.json()
      
      if (data.data && data.data.recent_launch_years) {
        setLaunchYears(data.data.recent_launch_years)
        if (data.data.recent_launch_years.length > 0) {
          setSelectedTimePeriod(data.data.recent_launch_years[0].year.toString())
        }
      }
    } catch (error) {
      console.error('Error fetching launch years:', error)
    }
  }

  const fetchObjects = async (pageNum = 0) => {
    setLoading(true)
    const params = new URLSearchParams()
    
    if (filters.search) params.append('q', filters.search)
    if (filters.country) params.append('country', filters.country)
    if (filters.status) params.append('status', filters.status)
    if (filters.orbital_band) params.append('orbital_band', filters.orbital_band)
    if (filters.congestion_risk) params.append('congestion_risk', filters.congestion_risk)
    if (filters.object_type) params.append('object_type', filters.object_type)
    
    if (sortConfig.length > 0) {
      const primarySort = sortConfig[0]
      params.append('sort_by', primarySort.column)
      params.append('sort_order', primarySort.direction.toUpperCase())
    }
    
    params.append('skip', pageNum * limit)
    params.append('limit', limit)

    try {
      const response = await apiFetch(`${API_ENDPOINTS.SEARCH}?${params}`)
      const data = await response.json()
      
      const objects = data.data.map(item => {
        const canonical = item.canonical || {}
        const orbit = canonical.orbit || {}
        
        return {
          'Identifier': item.identifier || '',
          'Object Name': canonical.object_name || canonical.name || '',
          'International Designator': canonical.international_designator || '',
          'Country of Origin': canonical.country || '',
          'Date of Launch': canonical.launch_date || '',
          'Function': canonical.function || '',
          'Status': canonical.status || '',
          'Orbital Band': canonical.orbital_band || '',
          'Congestion Risk': canonical.congestion_risk || '',
          'Object Type': canonical.object_type || '',
          'Apogee (km)': orbit.apogee_km,
          'Perigee (km)': orbit.perigee_km,
          'Inclination (degrees)': orbit.inclination_degrees,
          'Period (minutes)': orbit.period_minutes,
          'UN Registered': canonical.un_registered || '',
          'GSO Location': canonical.gso_location || '',
          'Secretariat Remarks': canonical.secretariat_remarks || '',
          'External Website': canonical.external_website || '',
          'Launch Vehicle': canonical.launch_vehicle || '',
          'Place of Launch': canonical.place_of_launch || '',
          'Registration Document': canonical.registration_document || '',
          '_mongodb_id': item.identifier,
          '_norad_id': canonical.norad_cat_id
        }
      })
      
      setObjects(objects)
      setTotal(data.count)
      setPage(pageNum)
      setSelectedObject(null)
    } catch (error) {
      console.error('Error fetching objects:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleLogin = (newToken, newIsDemo = false) => {
    setToken(newToken)
    setIsDemo(newIsDemo)
  }

  const handleLogout = async () => {
    try {
      await apiFetch('/v2/auth/logout', { method: 'POST' })
    } catch {
    }
    sessionStorage.removeItem('auth_token')
    sessionStorage.removeItem('is_demo')
    setToken(null)
    setIsDemo(false)
  }

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters)
  }

  const handleRowClick = (object) => {
    setSelectedObject(object)
  }

  const handleSort = (column) => {
    setSortConfig(prevConfig => {
      const existingIndex = prevConfig.findIndex(s => s.column === column)
      
      if (existingIndex === -1) {
        return [...prevConfig, { column, direction: 'asc' }]
      }
      
      const existing = prevConfig[existingIndex]
      if (existing.direction === 'asc') {
        const newConfig = [...prevConfig]
        newConfig[existingIndex] = { column, direction: 'desc' }
        return newConfig
      }
      
      return prevConfig.filter((_, index) => index !== existingIndex)
    })
  }

  const sortedObjects = [...objects].sort((a, b) => {
    for (const { column, direction } of sortConfig) {
      let aVal = a[column]
      let bVal = b[column]
      
      if (aVal === null || aVal === undefined || aVal === '') aVal = ''
      if (bVal === null || bVal === undefined || bVal === '') bVal = ''
      
      let comparison = 0
      
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        comparison = aVal - bVal
      } else {
        comparison = String(aVal).localeCompare(String(bVal))
      }
      
      if (comparison !== 0) {
        return direction === 'asc' ? comparison : -comparison
      }
    }
    return 0
  })

  if (!token) {
    return <LoginPage onLogin={handleLogin} />
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Space Object Registry</h1>
        <nav className="app-nav">
          <button 
            className={activeTab === 'table' ? 'active' : ''}
            onClick={() => setActiveTab('table')}
          >
            Table View
          </button>
          {!isDemo && (
            <button 
              className={activeTab === 'observations' ? 'active' : ''}
              onClick={() => setActiveTab('observations')}
            >
              Observations
            </button>
          )}
          <button 
            className={activeTab === 'graphs' ? 'active' : ''}
            onClick={() => setActiveTab('graphs')}
          >
            Graphs
          </button>
          <button 
            className={activeTab === 'timeline' ? 'active' : ''}
            onClick={() => setActiveTab('timeline')}
          >
            Timeline
          </button>
          <button 
            className={activeTab === 'analytics' ? 'active' : ''}
            onClick={() => setActiveTab('analytics')}
          >
            Analytics
          </button>
          <button 
            className={activeTab === 'admin' ? 'active' : ''}
            onClick={() => setActiveTab('admin')}
          >
            Admin
          </button>
        </nav>
        {activeTab === 'table' && <p>{total} objects</p>}
        {activeTab === 'observations' && <p>Observational Data</p>}
        <button className="logout-button" onClick={handleLogout}>Logout</button>
      </header>
      
      {activeTab === 'table' && (
        <div className="app-container">
          <aside className="sidebar">
            <Filters 
              filters={filters}
              filterOptions={filterOptions}
              onFilterChange={handleFilterChange}
            />
          </aside>
          
          <main className="main-content">
            <div className="table-container">
              <DataTable 
                objects={sortedObjects}
                selectedObject={selectedObject}
                onRowClick={handleRowClick}
                loading={loading}
                sortConfig={sortConfig}
                onSort={handleSort}
              />
              {total > limit && (
                <div className="pagination">
                  <button 
                    onClick={() => fetchObjects(page - 1)}
                    disabled={page === 0}
                  >
                    Previous
                  </button>
                  <span>Page {page + 1} of {Math.ceil(total / limit)}</span>
                  <button 
                    onClick={() => fetchObjects(page + 1)}
                    disabled={(page + 1) * limit >= total}
                  >
                    Next
                  </button>
                </div>
              )}
              
              <DetailPanel object={selectedObject} isDemo={isDemo} />
            </div>
          </main>
        </div>
      )}

      {activeTab === 'observations' && !isDemo && (
        <ObservationsView />
      )}

      {activeTab === 'graphs' && (
        <div className="graph-view-container">
          <GraphExplorer />
        </div>
      )}

      {activeTab === 'timeline' && (
        <div className="timeline-view-container">
          <div className="timeline-sidebar">
            <h3>Launch Years</h3>
            <p className="section-description">Select a year to view breakdown ({UI_TEXT.TIMELINE_COVERAGE})</p>
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
          </div>
          <div className="timeline-main">
            <TimelineChart selectedTimePeriod={selectedTimePeriod} />
          </div>
        </div>
      )}

      {activeTab === 'admin' && (
        <div className="analytics-view-container">
          <AdminPage />
        </div>
      )}

      {activeTab === 'analytics' && (
        <div className="analytics-view-container">
          <div className="analytics-sidebar">
            <h3>Analytics</h3>
            <p className="section-description">Select an analytics page</p>
            <div className="item-list">
              {analyticsPages.map((page) => (
                <div
                  key={page.id}
                  className={`list-item ${selectedAnalytics === page.id ? 'selected' : ''}`}
                  onClick={() => setSelectedAnalytics(page.id)}
                >
                  <div className="item-name">{page.name}</div>
                  <div className="item-description">{page.description}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="analytics-main">
            {selectedAnalytics === 'function-similarity' && <FunctionAnalytics />}
            {selectedAnalytics === 'registration-docs' && <RegistrationDocumentAnalytics />}
          </div>
        </div>
      )}
    </div>
  )
}

export default App


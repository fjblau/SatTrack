import { useState, useEffect } from 'react'
import './App.css'
import DataTable from './components/DataTable'
import DetailPanel from './components/DetailPanel'
import Filters from './components/Filters'
import GraphExplorer from './components/GraphExplorer'

function App() {
  const [activeTab, setActiveTab] = useState('table')
  const [objects, setObjects] = useState([])
  const [filters, setFilters] = useState({})
  const [selectedObject, setSelectedObject] = useState(null)
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [filterOptions, setFilterOptions] = useState({})

  const limit = 50

  useEffect(() => {
    fetchFilterOptions()
  }, [])

  useEffect(() => {
    fetchObjects()
    setPage(0)
  }, [filters])

  const fetchFilterOptions = async () => {
    try {
      const [countriesRes, statusesRes, orbitalBandsRes, congestionRisksRes] = await Promise.all([
        fetch('/v2/countries'),
        fetch('/v2/statuses'),
        fetch('/v2/orbital-bands'),
        fetch('/v2/congestion-risks')
      ])
      const countriesData = await countriesRes.json()
      const statusesData = await statusesRes.json()
      const orbitalBandsData = await orbitalBandsRes.json()
      const congestionRisksData = await congestionRisksRes.json()
      
      setFilterOptions({
        countries: countriesData.countries || [],
        statuses: statusesData.statuses || [],
        orbital_bands: orbitalBandsData.orbital_bands || [],
        congestion_risks: congestionRisksData.congestion_risks || [],
        apogee_range: [0, 100000],
        perigee_range: [0, 100000],
        inclination_range: [0, 180]
      })
    } catch (error) {
      console.error('Error fetching filters:', error)
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
    
    params.append('skip', pageNum * limit)
    params.append('limit', limit)

    try {
      const response = await fetch(`/v2/search?${params}`)
      const data = await response.json()
      
      const objects = data.data.map(item => {
        const canonical = item.canonical || {}
        const orbit = canonical.orbit || {}
        
        return {
          'Registration Number': canonical.registration_number || '',
          'Object Name': canonical.object_name || canonical.name || '',
          'International Designator': canonical.international_designator || '',
          'Country of Origin': canonical.country_of_origin || '',
          'Date of Launch': canonical.date_of_launch || '',
          'Function': canonical.function || '',
          'Status': canonical.status || '',
          'Orbital Band': canonical.orbital_band || '',
          'Congestion Risk': canonical.congestion_risk || '',
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

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters)
  }

  const handleRowClick = (object) => {
    setSelectedObject(object)
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
          <button 
            className={activeTab === 'graphs' ? 'active' : ''}
            onClick={() => setActiveTab('graphs')}
          >
            Graph View
          </button>
        </nav>
        {activeTab === 'table' && <p>{total} objects</p>}
      </header>
      
      {activeTab === 'table' ? (
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
                objects={objects}
                selectedObject={selectedObject}
                onRowClick={handleRowClick}
                loading={loading}
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
            </div>
            
            <DetailPanel object={selectedObject} />
          </main>
        </div>
      ) : (
        <div className="graph-view-container">
          <GraphExplorer />
        </div>
      )}
    </div>
  )
}

export default App


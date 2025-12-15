import { useState, useEffect } from 'react'
import './App.css'
import DataTable from './components/DataTable'
import DetailPanel from './components/DetailPanel'
import Filters from './components/Filters'

function App() {
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
      const response = await fetch('/api/filters')
      const data = await response.json()
      setFilterOptions(data)
    } catch (error) {
      console.error('Error fetching filters:', error)
    }
  }

  const fetchObjects = async (pageNum = 0) => {
    setLoading(true)
    const params = new URLSearchParams()
    
    if (filters.search) params.append('search', filters.search)
    if (filters.country) params.append('country', filters.country)
    if (filters.function) params.append('function', filters.function)
    if (filters.apogee_min !== undefined) params.append('apogee_min', filters.apogee_min)
    if (filters.apogee_max !== undefined) params.append('apogee_max', filters.apogee_max)
    if (filters.perigee_min !== undefined) params.append('perigee_min', filters.perigee_min)
    if (filters.perigee_max !== undefined) params.append('perigee_max', filters.perigee_max)
    if (filters.inclination_min !== undefined) params.append('inclination_min', filters.inclination_min)
    if (filters.inclination_max !== undefined) params.append('inclination_max', filters.inclination_max)
    
    params.append('skip', pageNum * limit)
    params.append('limit', limit)

    try {
      const response = await fetch(`/api/objects?${params}`)
      const data = await response.json()
      setObjects(data.data)
      setTotal(data.total)
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
        <h1>UNOOSA Space Object Registry</h1>
        <p>{total} objects</p>
      </header>
      
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
    </div>
  )
}

export default App

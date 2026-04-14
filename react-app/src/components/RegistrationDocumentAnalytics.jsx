import apiFetch from '../utils/apiFetch'
import { useState, useEffect } from 'react'
import './RegistrationDocumentAnalytics.css'
import { API_ENDPOINTS } from '../config/constants'

function RegistrationDocumentAnalytics() {
  const [loading, setLoading] = useState(false)
  const [documents, setDocuments] = useState([])
  const [stats, setStats] = useState(null)
  const [sortBy, setSortBy] = useState('satellite_count')
  const [sortOrder, setSortOrder] = useState('DESC')
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    loadDocumentData()
  }, [sortBy, sortOrder, searchTerm])

  const loadDocumentData = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      params.append('sort_by', sortBy)
      params.append('sort_order', sortOrder)
      if (searchTerm) {
        params.append('search', searchTerm)
      }

      const response = await apiFetch(`${API_ENDPOINTS.GRAPHS.REGISTRATION_DOCUMENTS_ANALYTICS}?${params}`)
      const data = await response.json()
      
      if (data.data) {
        setDocuments(data.data.documents || [])
        setStats(data.data.stats || null)
      }
    } catch (error) {
      console.error('Error loading registration document analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'ASC' ? 'DESC' : 'ASC')
    } else {
      setSortBy(field)
      setSortOrder('DESC')
    }
  }

  const getSortIcon = (field) => {
    if (sortBy !== field) return '⇅'
    return sortOrder === 'ASC' ? '↑' : '↓'
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    try {
      const date = new Date(dateString)
      return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
      })
    } catch {
      return 'N/A'
    }
  }

  const handleDocumentClick = async (e, url) => {
    e.preventDefault()
    try {
      const response = await apiFetch(`${API_ENDPOINTS.DOCUMENTS.RESOLVE}?path=${encodeURIComponent(url)}`)
      const data = await response.json()
      const target = data.english_link || data.original_url || `https://www.unoosa.org${url}`
      window.open(target, '_blank', 'noopener,noreferrer')
    } catch {
      window.open(`https://www.unoosa.org${url}`, '_blank', 'noopener,noreferrer')
    }
  }

  const truncateUrl = (url, maxLength = 60) => {
    if (url.length <= maxLength) return url
    return url.substring(0, maxLength) + '...'
  }

  const renderStatistics = () => {
    if (!stats) return null

    return (
      <div className="summary-cards">
        <div className="summary-card">
          <div className="card-value">{stats.total_documents?.toLocaleString() || '0'}</div>
          <div className="card-label">Total Documents</div>
        </div>
        <div className="summary-card">
          <div className="card-value">{stats.total_satellites?.toLocaleString() || '0'}</div>
          <div className="card-label">Total Satellites</div>
        </div>
        <div className="summary-card">
          <div className="card-value">{stats.avg_satellites_per_doc?.toFixed(1) || '0'}</div>
          <div className="card-label">Avg Sats/Doc</div>
        </div>
        <div className="summary-card">
          <div className="card-value">{stats.top_country || 'N/A'}</div>
          <div className="card-label">Top Country</div>
        </div>
      </div>
    )
  }

  const renderTable = () => {
    if (documents.length === 0) {
      return (
        <div className="no-data">
          {searchTerm ? `No documents found matching "${searchTerm}"` : 'No registration documents available'}
        </div>
      )
    }

    return (
      <div className="table-wrapper">
        <table className="documents-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('url')} className="sortable">
                URL {getSortIcon('url')}
              </th>
              <th onClick={() => handleSort('satellite_count')} className="sortable">
                Satellite Count {getSortIcon('satellite_count')}
              </th>
              <th>Countries</th>
              <th onClick={() => handleSort('created_at')} className="sortable">
                Created At {getSortIcon('created_at')}
              </th>
            </tr>
          </thead>
          <tbody>
            {documents.map(doc => (
              <tr key={doc.key}>
                <td className="url-cell">
                  <a 
                    href={`https://www.unoosa.org${doc.url}`}
                    onClick={(e) => handleDocumentClick(e, doc.url)}
                    rel="noopener noreferrer"
                    title={doc.url}
                  >
                    {truncateUrl(doc.url)}
                  </a>
                </td>
                <td className="count-cell">{doc.satellite_count?.toLocaleString() || 0}</td>
                <td className="countries-cell">
                  {doc.countries && doc.countries.length > 0 
                    ? doc.countries.slice(0, 5).join(', ') + (doc.countries.length > 5 ? '...' : '')
                    : 'N/A'
                  }
                </td>
                <td className="date-cell">{formatDate(doc.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="registration-document-analytics">
      <div className="analytics-header">
        <h2>Registration Documents Analytics</h2>
        <div className="search-box">
          <input
            type="text"
            placeholder="Search by URL..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {loading ? (
        <div className="loading">Loading registration document data...</div>
      ) : (
        <div className="analytics-content">
          {renderStatistics()}
          <div className="table-container">
            <h3>Registration Documents</h3>
            <p className="description">
              Overview of all registration documents with satellite counts, associated countries, and creation dates.
              Click column headers to sort.
            </p>
            {renderTable()}
          </div>
        </div>
      )}
    </div>
  )
}

export default RegistrationDocumentAnalytics

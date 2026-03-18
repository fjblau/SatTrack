import apiFetch from '../utils/apiFetch'
import { useState, useEffect, useRef } from 'react'
import './AdminPage.css'

function AdminPage() {
  const [scripts, setScripts] = useState([])
  const [loading, setLoading] = useState(false)
  const [runs, setRuns] = useState({})
  const pollTimers = useRef({})

  useEffect(() => {
    fetchScripts()
    return () => {
      Object.values(pollTimers.current).forEach(clearInterval)
    }
  }, [])

  const fetchScripts = async () => {
    setLoading(true)
    try {
      const response = await apiFetch('/v2/admin/scripts')
      const data = await response.json()
      setScripts(data.scripts || [])
    } catch (error) {
      console.error('Error fetching scripts:', error)
    } finally {
      setLoading(false)
    }
  }

  const runScript = async (scriptId) => {
    try {
      const response = await apiFetch(`/v2/admin/scripts/${scriptId}/run`, {
        method: 'POST'
      })
      const data = await response.json()
      const runId = data.run_id

      setRuns(prev => ({
        ...prev,
        [scriptId]: { runId, status: 'running', output: '' }
      }))

      pollTimers.current[scriptId] = setInterval(() => pollRun(scriptId, runId), 2000)
    } catch (error) {
      console.error('Error running script:', error)
      setRuns(prev => ({
        ...prev,
        [scriptId]: { runId: null, status: 'error', output: String(error) }
      }))
    }
  }

  const pollRun = async (scriptId, runId) => {
    try {
      const response = await apiFetch(`/v2/admin/runs/${runId}`)
      const data = await response.json()

      setRuns(prev => ({
        ...prev,
        [scriptId]: { runId, status: data.status, output: data.output || '' }
      }))

      if (data.status === 'success' || data.status === 'error') {
        clearInterval(pollTimers.current[scriptId])
        delete pollTimers.current[scriptId]
      }
    } catch (error) {
      console.error('Error polling run:', error)
    }
  }

  const categories = [...new Set(scripts.map(s => s.category))]

  return (
    <div className="admin-page">
      <div className="admin-header">
        <h2>Data Enrichment Scripts</h2>
      </div>

      {loading && <div className="admin-loading">Loading scripts...</div>}

      {!loading && categories.map(category => (
        <div key={category} className="script-category">
          <h3 className="category-title">{category.charAt(0).toUpperCase() + category.slice(1)}</h3>
          <div className="script-list">
            {scripts.filter(s => s.category === category).map(script => {
              const run = runs[script.id]
              const isRunning = run?.status === 'running'

              return (
                <div key={script.id} className="script-card">
                  <div className="script-card-header">
                    <div className="script-info">
                      <div className="script-name">{script.name}</div>
                      <div className="script-description">{script.description}</div>
                    </div>
                    <div className="script-controls">
                      <span className={`status-badge status-${run?.status || 'idle'}`}>
                        {run?.status || 'idle'}
                      </span>
                      <button
                        className="run-button"
                        onClick={() => runScript(script.id)}
                        disabled={isRunning}
                      >
                        {isRunning ? 'Running...' : 'Run'}
                      </button>
                    </div>
                  </div>
                  {run?.output && (
                    <pre className="script-log">{run.output}</pre>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

export default AdminPage

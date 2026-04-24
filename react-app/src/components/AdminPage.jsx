import apiFetch from '../utils/apiFetch'
import { useState, useEffect, useRef } from 'react'
import './AdminPage.css'

function AdminPage() {
  const [scripts, setScripts] = useState([])
  const [loading, setLoading] = useState(false)
  const [runs, setRuns] = useState({})
  const [uploads, setUploads] = useState({})
  const pollTimers = useRef({})
  const fileInputRefs = useRef({})

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

  const handleFileChange = async (scriptId, acceptedExtensions, e) => {
    const file = e.target.files[0]
    if (!file) return

    setUploads(prev => ({ ...prev, [scriptId]: { status: 'uploading', filename: file.name } }))

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await apiFetch(`/v2/admin/scripts/${scriptId}/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Upload failed')
      }

      const data = await response.json()
      setUploads(prev => ({ ...prev, [scriptId]: { status: 'ready', filename: data.filename } }))
    } catch (error) {
      setUploads(prev => ({ ...prev, [scriptId]: { status: 'error', filename: file.name, error: String(error) } }))
    }
  }

  const runScript = async (scriptId) => {
    try {
      const response = await apiFetch(`/v2/admin/scripts/${scriptId}/run`, {
        method: 'POST'
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Run failed')
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
        [scriptId]: {
          runId,
          status: data.status,
          output: data.output || '',
          backupDir: data.backup_dir || null,
        }
      }))

      if (data.status === 'success' || data.status === 'error') {
        clearInterval(pollTimers.current[scriptId])
        delete pollTimers.current[scriptId]
      }
    } catch (error) {
      console.error('Error polling run:', error)
    }
  }

  const downloadBackup = (runId) => {
    const url = `/api/v2/admin/runs/${runId}/download`
    const a = document.createElement('a')
    a.href = url
    a.download = ''
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
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
              const upload = uploads[script.id]
              const isRunning = run?.status === 'running'
              const needsFile = script.requires_file
              const canRun = !needsFile || upload?.status === 'ready'
              const accept = (script.accepted_extensions || []).join(',')

              return (
                <div key={script.id} className="script-card">
                  <div className="script-card-header">
                    <div className="script-info">
                      <div className="script-name">{script.name}</div>
                      <div className="script-description">{script.description}</div>
                    </div>
                    <div className="script-controls">
                      {needsFile && (
                        <div className="upload-control">
                          <input
                            type="file"
                            accept={accept}
                            ref={el => fileInputRefs.current[script.id] = el}
                            style={{ display: 'none' }}
                            onChange={e => handleFileChange(script.id, script.accepted_extensions, e)}
                          />
                          <button
                            className={`upload-button ${upload?.status === 'ready' ? 'upload-ready' : ''}`}
                            onClick={() => fileInputRefs.current[script.id]?.click()}
                            disabled={isRunning || upload?.status === 'uploading'}
                            title={upload?.filename || 'Choose file to upload'}
                          >
                            {upload?.status === 'uploading'
                              ? 'Uploading...'
                              : upload?.status === 'ready'
                              ? `\u2713 ${upload.filename}`
                              : 'Upload File'}
                          </button>
                          {upload?.status === 'error' && (
                            <span className="upload-error" title={upload.error}>Upload failed</span>
                          )}
                        </div>
                      )}
                      <span className={`status-badge status-${run?.status || 'idle'}`}>
                        {run?.status || 'idle'}
                      </span>
                      <button
                        className="run-button"
                        onClick={() => runScript(script.id)}
                        disabled={isRunning || !canRun}
                        title={needsFile && !canRun ? 'Upload a file first' : undefined}
                      >
                        {isRunning ? 'Running...' : 'Run'}
                      </button>
                    </div>
                  </div>
                  {run?.status === 'success' && run?.backupDir && (
                    <div className="backup-download-bar">
                      <span className="backup-ready-label">Backup ready</span>
                      <button
                        className="download-button"
                        onClick={() => downloadBackup(run.runId)}
                      >
                        Download Backup (.zip)
                      </button>
                    </div>
                  )}
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

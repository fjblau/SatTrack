import apiFetch from '../utils/apiFetch'
import { useState, useEffect, useRef } from 'react'
import './AdminPage.css'

const DEMO_CONTENTS_KEY = 'demoContentsConfig'

const DEMO_TABS = [
  {
    id: 'satellite-catalog',
    label: 'Satellite Catalog',
    defaultEnabled: true,
    subtabs: [
      { id: 'table', label: 'Satellite Catalog' },
      { id: 'satellite-graphs', label: 'Satellite Graphs' },
      { id: 'function-similarity', label: 'Function Similarity' },
      { id: 'registration-docs', label: 'Registration Docs' },
      { id: 'timeline', label: 'Timeline' },
      { id: 'by-class', label: 'By Class' },
    ]
  },
  {
    id: 'kestrel-mission',
    label: 'Kestrel Mission',
    defaultEnabled: true,
    subtabs: [
      { id: 'launch', label: 'Intercept Setup' },
      { id: 'maneuver', label: 'Maneuver Plan' },
      { id: 'advisor', label: 'AI Mission Advisor' },
      { id: 'gmatplan', label: 'GMAT Maneuver Plan' },
      { id: 'collection', label: 'Data Collection' },
    ]
  },
  {
    id: 'kestrel-data',
    label: 'Kestrel Data',
    defaultEnabled: true,
    subtabs: [
      { id: 'globe', label: '3D Globe View' },
      { id: 'observations', label: 'Observation Log' },
    ]
  },
  {
    id: 'aql-editor',
    label: 'AQL Editor',
    defaultEnabled: false,
    subtabs: []
  },
  {
    id: 'ephemeris',
    label: 'Ephemeris',
    defaultEnabled: false,
    subtabs: []
  },
  {
    id: 'fragmentation-events',
    label: 'Fragmentation',
    defaultEnabled: false,
    subtabs: []
  },
  {
    id: 'provenance',
    label: 'Provenance',
    defaultEnabled: false,
    subtabs: []
  },
  {
    id: 'help',
    label: '? Help',
    defaultEnabled: true,
    subtabs: []
  }
]

const getDefaultDemoConfig = () => {
  const config = {}
  DEMO_TABS.forEach(tab => {
    const enabled = tab.defaultEnabled !== false
    config[tab.id] = { enabled, subtabs: {} }
    tab.subtabs.forEach(subtab => {
      config[tab.id].subtabs[subtab.id] = enabled
    })
  })
  return config
}

const loadDemoConfig = () => {
  try {
    const stored = localStorage.getItem(DEMO_CONTENTS_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      const defaults = getDefaultDemoConfig()
      const merged = { ...defaults }
      Object.keys(parsed).forEach(tabId => {
        if (merged[tabId]) {
          merged[tabId] = {
            ...merged[tabId],
            ...parsed[tabId],
            subtabs: { ...merged[tabId].subtabs, ...parsed[tabId].subtabs }
          }
        }
      })
      return merged
    }
  } catch {}
  return getDefaultDemoConfig()
}

function AdminPage() {
  const [scripts, setScripts] = useState([])
  const [loading, setLoading] = useState(false)
  const [runs, setRuns] = useState({})
  const [uploads, setUploads] = useState({})
  const [backups, setBackups] = useState([])
  const [backupsLoading, setBackupsLoading] = useState(false)
  const [downloadingBackup, setDownloadingBackup] = useState(null)
  const [demoConfig, setDemoConfig] = useState(loadDemoConfig)
  const pollTimers = useRef({})
  const fileInputRefs = useRef({})

  const saveDemoConfig = (newConfig) => {
    setDemoConfig(newConfig)
    localStorage.setItem(DEMO_CONTENTS_KEY, JSON.stringify(newConfig))
  }

  const handleTabToggle = (tabId) => {
    const newEnabled = !demoConfig[tabId].enabled
    const newSubtabs = {}
    Object.keys(demoConfig[tabId].subtabs).forEach(subId => {
      newSubtabs[subId] = newEnabled
    })
    saveDemoConfig({
      ...demoConfig,
      [tabId]: { ...demoConfig[tabId], enabled: newEnabled, subtabs: newSubtabs }
    })
  }

  const handleSubtabToggle = (tabId, subtabId) => {
    saveDemoConfig({
      ...demoConfig,
      [tabId]: {
        ...demoConfig[tabId],
        subtabs: { ...demoConfig[tabId].subtabs, [subtabId]: !demoConfig[tabId].subtabs[subtabId] }
      }
    })
  }

  useEffect(() => {
    fetchScripts()
    fetchBackups()
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

  const fetchBackups = async () => {
    setBackupsLoading(true)
    try {
      const response = await apiFetch('/v2/admin/backups')
      const data = await response.json()
      setBackups(data.backups || [])
    } catch (error) {
      console.error('Error fetching backups:', error)
    } finally {
      setBackupsLoading(false)
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
        fetchBackups()
      }
    } catch (error) {
      console.error('Error polling run:', error)
    }
  }

  const downloadBackup = async (runId) => {
    try {
      const response = await apiFetch(`/v2/admin/runs/${runId}/download`)
      if (!response.ok) throw new Error(`Download failed: ${response.status}`)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const disposition = response.headers.get('Content-Disposition') || ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match ? match[1] : `backup_${runId}.zip`
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Backup download failed:', error)
    }
  }

  const downloadBackupByName = async (dirName) => {
    setDownloadingBackup(dirName)
    try {
      const response = await apiFetch(`/v2/admin/backups/${encodeURIComponent(dirName)}/download`)
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || `Download failed: ${response.status}`)
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${dirName}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Backup download failed:', error)
      alert(`Download failed: ${error.message}`)
    } finally {
      setDownloadingBackup(null)
    }
  }

  const categories = [...new Set(scripts.map(s => s.category))]

  return (
    <div className="admin-page">
      <div className="admin-header">
        <h2>Data Enrichment Scripts</h2>
      </div>

      <div className="demo-contents-section">
        <div className="demo-contents-header">
          <h3 className="category-title">Demo Contents</h3>
          <p className="demo-contents-desc">Configure which tabs are visible when logged in as demo.</p>
        </div>
        <div className="demo-tab-list">
          {DEMO_TABS.map(tab => {
            const tabConfig = demoConfig[tab.id]
            return (
              <div key={tab.id} className="demo-tab-item">
                <label className="demo-tab-label">
                  <input
                    type="checkbox"
                    checked={tabConfig.enabled}
                    onChange={() => handleTabToggle(tab.id)}
                  />
                  <span className="demo-tab-name">{tab.label}</span>
                </label>
                {tab.subtabs.length > 0 && (
                  <div className="demo-subtab-list">
                    {tab.subtabs.map(subtab => (
                      <label
                        key={subtab.id}
                        className={`demo-subtab-label${!tabConfig.enabled ? ' demo-subtab-disabled' : ''}`}
                      >
                        <input
                          type="checkbox"
                          checked={tabConfig.subtabs[subtab.id]}
                          disabled={!tabConfig.enabled}
                          onChange={() => handleSubtabToggle(tab.id, subtab.id)}
                        />
                        <span className="demo-subtab-name">{subtab.label}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {backups.length > 0 && (
        <div className="backups-section">
          <div className="backups-section-header">
            <h3 className="category-title">Existing Backups on Server</h3>
            <button className="refresh-button" onClick={fetchBackups} disabled={backupsLoading}>
              {backupsLoading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
          <div className="backup-list">
            {backups.map(b => (
              <div key={b.name} className="backup-item">
                <div className="backup-item-info">
                  <span className="backup-item-name">{b.name}</span>
                  {b.exported_at && (
                    <span className="backup-item-meta">
                      {new Date(b.exported_at).toLocaleString()} — {b.total_documents?.toLocaleString() ?? '?'} docs
                    </span>
                  )}
                </div>
                <button
                  className="download-button"
                  onClick={() => downloadBackupByName(b.name)}
                  disabled={downloadingBackup === b.name}
                >
                  {downloadingBackup === b.name ? 'Downloading...' : 'Download .zip'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {backups.length === 0 && !backupsLoading && (
        <div className="backups-section">
          <div className="backups-section-header">
            <h3 className="category-title">Existing Backups on Server</h3>
            <button className="refresh-button" onClick={fetchBackups}>Refresh</button>
          </div>
          <div className="no-backups">No backups found on server.</div>
        </div>
      )}

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

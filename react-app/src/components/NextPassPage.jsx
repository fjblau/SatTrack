import { useState, useRef } from 'react'
import NextPassContent from './NextPassContent'
import './NextPassPage.css'

const SELECTOR_MODES = ['search', 'norad', 'tle']

function parseTleLines(text) {
  const lines = text.trim().split('\n').map(l => l.trim()).filter(Boolean)
  if (lines.length === 3) return { name: lines[0], line1: lines[1], line2: lines[2] }
  if (lines.length === 2) return { name: `NORAD ${lines[0].slice(2, 7).trim()}`, line1: lines[0], line2: lines[1] }
  return null
}

function validateTle(text) {
  const parsed = parseTleLines(text)
  if (!parsed) return 'Paste 2 lines (TLE line 1 + line 2) or 3 lines (name + line 1 + line 2)'
  if (!parsed.line1.startsWith('1 ')) return "Line 1 must start with '1 '"
  if (!parsed.line2.startsWith('2 ')) return "Line 2 must start with '2 '"
  return null
}

export default function NextPassPage() {
  const [mode, setMode] = useState('search')
  const [resolvedTarget, setResolvedTarget] = useState(null)

  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState(null)
  const searchDebounceRef = useRef(null)

  const [noradInput, setNoradInput] = useState('')
  const [noradError, setNoradError] = useState(null)

  const [tleText, setTleText] = useState('')
  const [tleError, setTleError] = useState(null)

  const runSearch = async (q) => {
    if (!q.trim()) { setSearchResults([]); return }
    setSearchLoading(true)
    setSearchError(null)
    try {
      const res = await fetch(`/v2/public/objects/search?q=${encodeURIComponent(q)}&limit=10`)
      if (!res.ok) throw new Error(`Search failed: ${res.status}`)
      const data = await res.json()
      setSearchResults(data.results || [])
      if ((data.results || []).length === 0) setSearchError('No objects found')
    } catch (err) {
      setSearchError(err.message)
    } finally {
      setSearchLoading(false)
    }
  }

  const handleSearchChange = (e) => {
    const q = e.target.value
    setSearchQuery(q)
    setSearchResults([])
    setSearchError(null)
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current)
    if (q.trim().length < 2) return
    searchDebounceRef.current = setTimeout(() => runSearch(q.trim()), 350)
  }

  const handleSelectObject = (item) => {
    setResolvedTarget({ type: 'norad', noradId: item.norad_id, name: item.name })
    setSearchQuery(item.name)
    setSearchResults([])
  }

  const handleNoradSubmit = () => {
    const id = noradInput.trim()
    if (!id || !/^\d+$/.test(id)) {
      setNoradError('Enter a valid numeric NORAD catalog ID')
      return
    }
    setNoradError(null)
    setResolvedTarget({ type: 'norad', noradId: id, name: `NORAD ${id}` })
  }

  const handleTleSubmit = () => {
    const err = validateTle(tleText)
    if (err) { setTleError(err); return }
    setTleError(null)
    const parsed = parseTleLines(tleText)
    setResolvedTarget({ type: 'tle', tleText, name: parsed.name })
  }

  const handleReset = () => {
    setResolvedTarget(null)
    setSearchQuery('')
    setSearchResults([])
    setSearchError(null)
    setNoradInput('')
    setNoradError(null)
    setTleText('')
    setTleError(null)
  }

  return (
    <div className="npp-root">
      <header className="npp-header">
        <div className="npp-header-inner">
          <span className="npp-logo-text">TALON</span>
          <h1 className="npp-title">Next Pass Predictor</h1>
          <span className="npp-subtitle">No account required</span>
        </div>
      </header>

      <main className="npp-main">
        {!resolvedTarget ? (
          <div className="npp-selector-card">
            <h2 className="npp-selector-heading">Select a satellite</h2>

            <div className="npp-mode-tabs">
              {[
                { id: 'search', label: 'Search by name' },
                { id: 'norad', label: 'NORAD ID' },
                { id: 'tle', label: 'Paste TLE' },
              ].map(tab => (
                <button
                  key={tab.id}
                  className={`npp-mode-tab${mode === tab.id ? ' active' : ''}`}
                  onClick={() => setMode(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {mode === 'search' && (
              <div className="npp-mode-panel">
                <p className="npp-mode-hint">Search the catalog by satellite name, NORAD ID, or international designator.</p>
                <div className="npp-search-row">
                  <input
                    className="npp-input"
                    type="text"
                    placeholder="e.g. ISS, Starlink-1234, 25544"
                    value={searchQuery}
                    onChange={handleSearchChange}
                    autoFocus
                  />
                  {searchLoading && <span className="npp-spinner">…</span>}
                </div>
                {searchError && <div className="npp-field-error">{searchError}</div>}
                {searchResults.length > 0 && (
                  <div className="npp-search-results">
                    {searchResults.map(item => (
                      <button
                        key={item.norad_id}
                        className="npp-result-item"
                        onClick={() => handleSelectObject(item)}
                        type="button"
                      >
                        <span className="npp-result-name">{item.name}</span>
                        <span className="npp-result-norad">NORAD {item.norad_id}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {mode === 'norad' && (
              <div className="npp-mode-panel">
                <p className="npp-mode-hint">Enter the NORAD catalog number directly (e.g. 25544 for ISS).</p>
                <div className="npp-search-row">
                  <input
                    className="npp-input"
                    type="text"
                    inputMode="numeric"
                    placeholder="e.g. 25544"
                    value={noradInput}
                    onChange={e => { setNoradInput(e.target.value); setNoradError(null) }}
                    onKeyDown={e => { if (e.key === 'Enter') handleNoradSubmit() }}
                    autoFocus
                  />
                  <button className="npp-submit-button" onClick={handleNoradSubmit}>
                    Use this ID →
                  </button>
                </div>
                {noradError && <div className="npp-field-error">{noradError}</div>}
              </div>
            )}

            {mode === 'tle' && (
              <div className="npp-mode-panel">
                <p className="npp-mode-hint">
                  Paste a 2-line or 3-line TLE (e.g. from{' '}
                  <a href="https://celestrak.org" target="_blank" rel="noopener noreferrer">CelesTrak</a>
                  ). Useful for objects not yet in the catalog or for custom TLEs.
                </p>
                <textarea
                  className="npp-tle-input"
                  rows={4}
                  placeholder={`ISS (ZARYA)\n1 25544U 98067A   24001.50000000  .00005000  00000-0  90000-4 0  9999\n2 25544  51.6400 340.0000 0001000  90.0000 270.0000 15.50000000 00001`}
                  value={tleText}
                  onChange={e => { setTleText(e.target.value); setTleError(null) }}
                  autoFocus
                  spellCheck={false}
                />
                <div className="npp-tle-actions">
                  <button className="npp-submit-button" onClick={handleTleSubmit}>
                    Use this TLE →
                  </button>
                </div>
                {tleError && <div className="npp-field-error">{tleError}</div>}
              </div>
            )}
          </div>
        ) : (
          <div className="npp-content-wrap">
            <div className="npp-content-header">
              <div className="npp-content-title">
                <h2>{resolvedTarget.name}</h2>
                {resolvedTarget.type === 'norad' && (
                  <span className="npp-content-norad">NORAD {resolvedTarget.noradId}</span>
                )}
                {resolvedTarget.type === 'tle' && (
                  <span className="npp-content-norad">Custom TLE</span>
                )}
              </div>
              <button className="npp-change-button" onClick={handleReset}>
                ← Change satellite
              </button>
            </div>
            <NextPassContent resolvedTarget={resolvedTarget} />
          </div>
        )}
      </main>

      <footer className="npp-footer">
        Pass predictions use SGP4 propagation · TLE data from CelesTrak
      </footer>
    </div>
  )
}

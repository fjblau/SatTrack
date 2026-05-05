import { useState, useEffect } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'

function EventDetail({ eventKey, onBack }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 25

  useEffect(() => {
    if (!eventKey) return
    let cancelled = false
    setLoading(true)
    setError(null)
    apiFetch(API_ENDPOINTS.PROVENANCE.EVENT(eventKey))
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(data => { if (!cancelled) setDetail(data) })
      .catch(err => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [eventKey])

  const evDoc = detail?.event
  const evCanonical = evDoc?.canonical || {}
  const fragments = detail?.fragments || []
  const pagedFragments = fragments.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(fragments.length / PAGE_SIZE)

  return (
    <div>
      <button
        onClick={onBack}
        style={{ marginBottom: '1rem', padding: '0.35rem 0.85rem', borderRadius: '6px', border: '1px solid #dee2e6', background: '#f8f9fa', cursor: 'pointer', fontSize: '0.85rem' }}
      >
        ← Back to Events
      </button>

      {loading && <p style={{ color: '#6c757d' }}>Loading event…</p>}
      {error && <p style={{ color: '#dc3545' }}>{error}</p>}

      {evDoc && (
        <>
          <h3 style={{ marginBottom: '0.5rem' }}>{evDoc.identifier || eventKey}</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
            {[
              { label: 'Event Type', value: evCanonical.event_type },
              { label: 'Epoch', value: evCanonical.epoch },
              { label: 'Altitude (km)', value: evCanonical.altitude_km },
              { label: 'Casualty Risk', value: evCanonical.casualty_risk },
              { label: 'Fragments (DISCOS)', value: detail.discos_fragment_count },
              { label: 'Fragments (DB)', value: detail.fragment_count },
            ].filter(x => x.value != null).map((x, i) => (
              <div key={i} style={{ background: '#f8f9fa', border: '1px solid #e9ecef', borderRadius: '6px', padding: '0.75rem' }}>
                <div style={{ fontSize: '0.72rem', color: '#6c757d', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>{x.label}</div>
                <div style={{ fontSize: '0.9rem', fontWeight: 500 }}>{String(x.value)}</div>
              </div>
            ))}
          </div>

          {fragments.length > 0 && (
            <>
              <h4 style={{ marginBottom: '0.5rem' }}>Fragments ({fragments.length})</h4>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                <thead>
                  <tr style={{ background: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
                    <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Object</th>
                    <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Class</th>
                    <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Status</th>
                    <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {pagedFragments.map((f, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                      <td style={{ padding: '0.45rem 0.75rem' }}>
                        {f.object?.canonical?.object_name || f.object?._key || '—'}
                      </td>
                      <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem' }}>
                        {f.object?.canonical?.object_class || '—'}
                      </td>
                      <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem' }}>
                        {f.object?.canonical?.status || '—'}
                      </td>
                      <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem' }}>
                        {f.confidence != null ? `${(f.confidence * 100).toFixed(0)}%` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {totalPages > 1 && (
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.75rem', justifyContent: 'flex-end' }}>
                  <button
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    disabled={page === 0}
                    style={{ padding: '0.3rem 0.7rem', borderRadius: '5px', border: '1px solid #dee2e6', background: '#fff', cursor: 'pointer' }}
                  >
                    Prev
                  </button>
                  <span style={{ fontSize: '0.85rem', color: '#6c757d' }}>Page {page + 1} of {totalPages}</span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    style={{ padding: '0.3rem 0.7rem', borderRadius: '5px', border: '1px solid #dee2e6', background: '#fff', cursor: 'pointer' }}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}

const AQL_ENDPOINT = API_ENDPOINTS.OBSERVATION_ANALYTICS.AQL

async function runAql(query) {
  const res = await apiFetch(AQL_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'AQL error')
  return data.data || []
}

export default function FragmentationEventsPage() {
  const [events, setEvents] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedKey, setSelectedKey] = useState(null)
  const [page, setPage] = useState(0)
  const [typeFilter, setTypeFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const PAGE_SIZE = 30

  const fetchEvents = async (pageNum = 0) => {
    setLoading(true)
    setError(null)
    try {
      const filters = []
      if (typeFilter) filters.push(`FILTER LOWER(ev.canonical.event_type) == LOWER("${typeFilter}")`)
      if (dateFrom) filters.push(`FILTER ev.canonical.epoch >= "${dateFrom}"`)
      if (dateTo) filters.push(`FILTER ev.canonical.epoch <= "${dateTo}"`)
      const filterStr = filters.join('\n  ')

      const aql = `
FOR ev IN fragmentation_events
  ${filterStr}
  SORT ev.canonical.epoch DESC
  LIMIT ${pageNum * PAGE_SIZE}, ${PAGE_SIZE}
  LET edge_fragment_count = LENGTH(FOR e IN caused_by FILTER e._to == ev._id RETURN 1)
  RETURN {
    _key: ev._key,
    identifier: ev.identifier,
    epoch: ev.canonical.epoch,
    event_type: ev.canonical.event_type,
    edge_fragment_count: edge_fragment_count,
    discos_fragment_count: ev.canonical.fragment_count,
    altitude_km: ev.canonical.altitude_km,
    comment: ev.canonical.comment
  }`.trim()

      const countAql = `
RETURN LENGTH(
  FOR ev IN fragmentation_events
    ${filterStr}
    RETURN 1
)`.trim()

      const [evData, countData] = await Promise.all([
        runAql(aql),
        runAql(countAql),
      ])

      setEvents(evData)
      setTotal(countData[0] || 0)
      setPage(pageNum)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEvents(0)
  }, [])

  if (selectedKey) {
    return (
      <div style={{ padding: '2rem', maxWidth: '1600px', margin: '0 auto', overflowY: 'auto', width: '100%' }}>
        <EventDetail eventKey={selectedKey} onBack={() => setSelectedKey(null)} />
      </div>
    )
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '1600px', margin: '0 auto', overflowY: 'auto', width: '100%' }}>
      <h2 style={{ marginBottom: '1rem' }}>Fragmentation Events</h2>

      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', color: '#6c757d', marginBottom: '0.2rem' }}>Event Type</label>
          <input
            type="text"
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}
            placeholder="e.g. explosion"
            style={{ padding: '0.35rem 0.6rem', borderRadius: '5px', border: '1px solid #dee2e6', fontSize: '0.875rem', width: '140px' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', color: '#6c757d', marginBottom: '0.2rem' }}>From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            style={{ padding: '0.35rem 0.6rem', borderRadius: '5px', border: '1px solid #dee2e6', fontSize: '0.875rem' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', color: '#6c757d', marginBottom: '0.2rem' }}>To</label>
          <input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
            style={{ padding: '0.35rem 0.6rem', borderRadius: '5px', border: '1px solid #dee2e6', fontSize: '0.875rem' }}
          />
        </div>
        <button
          onClick={() => fetchEvents(0)}
          disabled={loading}
          style={{ padding: '0.4rem 1rem', borderRadius: '6px', border: 'none', background: '#2980b9', color: '#fff', cursor: 'pointer', fontSize: '0.875rem' }}
        >
          {loading ? 'Loading…' : 'Apply'}
        </button>
        <button
          onClick={() => { setTypeFilter(''); setDateFrom(''); setDateTo(''); fetchEvents(0) }}
          style={{ padding: '0.4rem 0.85rem', borderRadius: '6px', border: '1px solid #dee2e6', background: '#f8f9fa', cursor: 'pointer', fontSize: '0.875rem' }}
        >
          Reset
        </button>
      </div>

      {error && (
        <div style={{ padding: '0.75rem 1rem', background: '#f8d7da', border: '1px solid #f5c6cb', borderRadius: '6px', color: '#721c24', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {loading && <p style={{ color: '#6c757d' }}>Loading events…</p>}

      {!loading && events.length === 0 && !error && (
        <p style={{ color: '#6c757d' }}>No fragmentation events found. Run DISCOS ingestion scripts from Admin to populate.</p>
      )}

      {events.length > 0 && (
        <>
          <p style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.5rem' }}>{total} events total</p>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ background: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Event</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Type</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Epoch</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Altitude (km)</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Comment</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'right' }}>Fragments (DISCOS)</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'right' }}>Fragments (DB)</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev, i) => (
                <tr
                  key={ev._key || i}
                  onClick={() => setSelectedKey(ev._key)}
                  style={{ borderBottom: '1px solid #f0f0f0', cursor: 'pointer' }}
                  onMouseEnter={e => e.currentTarget.style.background = '#f8f9fa'}
                  onMouseLeave={e => e.currentTarget.style.background = ''}
                >
                  <td style={{ padding: '0.45rem 0.75rem', fontWeight: 500, color: '#2980b9' }}>
                    {ev.identifier || ev._key}
                  </td>
                  <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem' }}>{ev.event_type || '—'}</td>
                  <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem' }}>{ev.epoch ? String(ev.epoch).slice(0, 10) : '—'}</td>
                  <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem' }}>
                    {ev.altitude_km != null ? ev.altitude_km.toLocaleString() : '—'}
                  </td>
                  <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem', maxWidth: '320px' }} title={ev.comment || undefined}>
                    {ev.comment ? ev.comment.slice(0, 80) + (ev.comment.length > 80 ? '…' : '') : '—'}
                  </td>
                  <td style={{ padding: '0.45rem 0.75rem', textAlign: 'right', color: '#6c757d', fontSize: '0.82rem' }}>
                    {ev.discos_fragment_count != null ? ev.discos_fragment_count.toLocaleString() : '—'}
                  </td>
                  <td style={{ padding: '0.45rem 0.75rem', textAlign: 'right', color: '#6c757d', fontSize: '0.82rem' }}>
                    {ev.edge_fragment_count != null ? ev.edge_fragment_count.toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {total > PAGE_SIZE && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.75rem', justifyContent: 'flex-end' }}>
              <button
                onClick={() => fetchEvents(page - 1)}
                disabled={page === 0 || loading}
                style={{ padding: '0.3rem 0.7rem', borderRadius: '5px', border: '1px solid #dee2e6', background: '#fff', cursor: 'pointer' }}
              >
                Prev
              </button>
              <span style={{ fontSize: '0.85rem', color: '#6c757d' }}>Page {page + 1} of {Math.ceil(total / PAGE_SIZE)}</span>
              <button
                onClick={() => fetchEvents(page + 1)}
                disabled={(page + 1) * PAGE_SIZE >= total || loading}
                style={{ padding: '0.3rem 0.7rem', borderRadius: '5px', border: '1px solid #dee2e6', background: '#fff', cursor: 'pointer' }}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

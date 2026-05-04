import { useState, useEffect } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS, OBJECT_CLASSES } from '../config/constants'

const PAGE_SIZE = 50

const CLASS_COLORS = {
  'Payload': '#2ecc71',
  'Rocket Body': '#e67e22',
  'Mission-Related Object': '#3498db',
  'Rocket Fragmentation Debris': '#e74c3c',
  'Payload Fragmentation Debris': '#c0392b',
  'Unknown': '#95a5a6',
}

function ClassStats({ stats }) {
  if (!stats || stats.length === 0) return null
  const total = stats.reduce((s, x) => s + (x.count || 0), 0)
  return (
    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
      {stats.map(s => {
        const pct = total > 0 ? ((s.count / total) * 100).toFixed(1) : '0'
        const color = CLASS_COLORS[s.class] || '#95a5a6'
        return (
          <div key={s.class} style={{ background: '#f8f9fa', border: '1px solid #e9ecef', borderRadius: '6px', padding: '0.6rem 0.85rem', minWidth: '150px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.2rem' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: color, flexShrink: 0 }} />
              <span style={{ fontSize: '0.75rem', color: '#6c757d', fontWeight: 600 }}>{s.class || 'Unknown'}</span>
            </div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>{(s.count || 0).toLocaleString()}</div>
            <div style={{ fontSize: '0.72rem', color: '#adb5bd' }}>{pct}% of total</div>
          </div>
        )
      })}
    </div>
  )
}

export default function CatalogByClassPage() {
  const [selectedClass, setSelectedClass] = useState(OBJECT_CLASSES[0])
  const [objects, setObjects] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState([])
  const [statsLoading, setStatsLoading] = useState(false)

  useEffect(() => {
    setStatsLoading(true)
    apiFetch(API_ENDPOINTS.OBJECTS.STATS)
      .then(r => r.json())
      .then(data => {
        setStats(data.by_class || [])
      })
      .catch(() => {})
      .finally(() => setStatsLoading(false))
  }, [])

  const fetchObjects = async (cls, pageNum = 0) => {
    setLoading(true)
    setError(null)
    try {
      const url = `${API_ENDPOINTS.OBJECTS.BY_CLASS(cls)}?skip=${pageNum * PAGE_SIZE}&limit=${PAGE_SIZE}`
      const res = await apiFetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setObjects(data.data || [])
      setTotal(data.count || 0)
      setPage(pageNum)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchObjects(selectedClass, 0)
  }, [selectedClass])

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '0.5rem' }}>Catalog by Object Class</h2>
      <p style={{ color: '#6c757d', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
        Browse the full catalog grouped by the post-Spec-1 object class taxonomy.
      </p>

      {!statsLoading && <ClassStats stats={stats} />}

      <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
        {OBJECT_CLASSES.map(cls => (
          <button
            key={cls}
            onClick={() => { setSelectedClass(cls); setPage(0) }}
            style={{
              padding: '0.35rem 0.85rem',
              borderRadius: '20px',
              border: `2px solid ${CLASS_COLORS[cls] || '#dee2e6'}`,
              background: selectedClass === cls ? (CLASS_COLORS[cls] || '#dee2e6') : '#fff',
              color: selectedClass === cls ? '#fff' : '#495057',
              cursor: 'pointer',
              fontSize: '0.82rem',
              fontWeight: selectedClass === cls ? 600 : 400,
              transition: 'all 0.15s',
            }}
          >
            {cls}
          </button>
        ))}
      </div>

      {error && (
        <div style={{ padding: '0.75rem 1rem', background: '#f8d7da', border: '1px solid #f5c6cb', borderRadius: '6px', color: '#721c24', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {loading && <p style={{ color: '#6c757d' }}>Loading…</p>}

      {!loading && objects.length === 0 && !error && (
        <p style={{ color: '#6c757d' }}>No objects found in this class.</p>
      )}

      {objects.length > 0 && (
        <>
          <p style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.5rem' }}>
            {total.toLocaleString()} objects in <strong>{selectedClass}</strong>
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ background: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Name</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>COSPAR</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Country</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Status</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Launch Date</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Orbital Band</th>
                <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left' }}>Identifiers</th>
              </tr>
            </thead>
            <tbody>
              {objects.map((obj, i) => {
                const c = obj.canonical || {}
                const aliases = obj.identifier_aliases || {}
                const aliasStr = Object.entries(aliases)
                  .filter(([, v]) => v != null && v !== '')
                  .map(([k, v]) => `${k}:${v}`)
                  .join(' ')
                return (
                  <tr key={obj.identifier || i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '0.45rem 0.75rem', fontWeight: 500 }}>{c.object_name || c.name || '—'}</td>
                    <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem' }}>{c.international_designator || '—'}</td>
                    <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem' }}>{c.country || '—'}</td>
                    <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem' }}>{c.status || '—'}</td>
                    <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem' }}>{c.launch_date ? String(c.launch_date).slice(0, 10) : '—'}</td>
                    <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.82rem' }}>{c.orbital_band || '—'}</td>
                    <td style={{ padding: '0.45rem 0.75rem', color: '#6c757d', fontSize: '0.75rem', maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={aliasStr}>
                      {aliasStr || '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {total > PAGE_SIZE && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.75rem', justifyContent: 'flex-end' }}>
              <button
                onClick={() => fetchObjects(selectedClass, page - 1)}
                disabled={page === 0 || loading}
                style={{ padding: '0.3rem 0.7rem', borderRadius: '5px', border: '1px solid #dee2e6', background: '#fff', cursor: 'pointer' }}
              >
                Prev
              </button>
              <span style={{ fontSize: '0.85rem', color: '#6c757d' }}>Page {page + 1} of {Math.ceil(total / PAGE_SIZE)}</span>
              <button
                onClick={() => fetchObjects(selectedClass, page + 1)}
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

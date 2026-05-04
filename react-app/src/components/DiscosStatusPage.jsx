import { useState, useEffect } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'

function StatusBadge({ status }) {
  const colors = {
    ready: { bg: '#d4edda', color: '#155724', border: '#c3e6cb' },
    not_configured: { bg: '#fff3cd', color: '#856404', border: '#ffc107' },
    error: { bg: '#f8d7da', color: '#721c24', border: '#f5c6cb' },
  }
  const style = colors[status] || colors.error
  return (
    <span style={{
      display: 'inline-block',
      padding: '0.2rem 0.6rem',
      borderRadius: '4px',
      fontSize: '0.8rem',
      fontWeight: 600,
      background: style.bg,
      color: style.color,
      border: `1px solid ${style.border}`,
    }}>
      {status?.replace('_', ' ').toUpperCase() || 'UNKNOWN'}
    </span>
  )
}

function InfoRow({ label, value }) {
  return (
    <div style={{ display: 'flex', gap: '1rem', padding: '0.4rem 0', borderBottom: '1px solid #f0f0f0', fontSize: '0.9rem' }}>
      <span style={{ minWidth: '180px', color: '#6c757d', fontWeight: 500 }}>{label}</span>
      <span style={{ flex: 1, wordBreak: 'break-all' }}>{value ?? '—'}</span>
    </div>
  )
}

export default function DiscosStatusPage() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchStatus = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch(API_ENDPOINTS.ADMIN.DISCOS_STATUS)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setStatus(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
  }, [])

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0 }}>DISCOS Integration Status</h2>
        <button
          onClick={fetchStatus}
          disabled={loading}
          style={{ padding: '0.35rem 0.85rem', borderRadius: '6px', border: '1px solid #dee2e6', background: '#f8f9fa', cursor: 'pointer', fontSize: '0.85rem' }}
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div style={{ padding: '0.75rem 1rem', background: '#f8d7da', border: '1px solid #f5c6cb', borderRadius: '6px', color: '#721c24', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {loading && !status && (
        <p style={{ color: '#6c757d' }}>Loading DISCOS status…</p>
      )}

      {status && (
        <div style={{ background: '#fff', border: '1px solid #dee2e6', borderRadius: '8px', overflow: 'hidden' }}>
          <div style={{ padding: '1rem 1.25rem', background: '#f8f9fa', borderBottom: '1px solid #dee2e6', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontWeight: 600 }}>Overall Status</span>
            <StatusBadge status={status.status} />
          </div>

          <div style={{ padding: '1rem 1.25rem' }}>
            <InfoRow label="Token Configured" value={status.token_configured ? 'Yes' : 'No — set DISCOS_API_TOKEN'} />
            <InfoRow label="Base URL" value={status.base_url} />

            {status.health_check && (
              <>
                <div style={{ marginTop: '1rem', marginBottom: '0.25rem', fontWeight: 600, fontSize: '0.85rem', color: '#495057' }}>
                  Health Check
                </div>
                <InfoRow label="Status" value={status.health_check.status} />
                {status.health_check.message && (
                  <InfoRow label="Message" value={status.health_check.message} />
                )}
                {status.health_check.rate_limit_remaining != null && (
                  <InfoRow label="Rate Limit Remaining" value={status.health_check.rate_limit_remaining} />
                )}
                {status.health_check.rate_limit_reset != null && (
                  <InfoRow label="Rate Limit Reset" value={new Date(status.health_check.rate_limit_reset * 1000).toLocaleString()} />
                )}
                {status.health_check.error && (
                  <InfoRow label="Error" value={status.health_check.error} />
                )}
              </>
            )}

            {!status.token_configured && (
              <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: '#fff3cd', border: '1px solid #ffc107', borderRadius: '6px', fontSize: '0.875rem', color: '#856404' }}>
                To enable DISCOS integration, set the <code>DISCOS_API_TOKEN</code> environment variable and restart the server.
                Request a token from the{' '}
                <a href="https://discosweb.esoc.esa.int" target="_blank" rel="noopener noreferrer">ESA DISCOS web portal</a>.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

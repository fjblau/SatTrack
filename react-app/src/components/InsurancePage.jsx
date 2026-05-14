import { useState, useEffect } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import InsuredAssetDetail from './InsuredAssetDetail'
import InsuranceAggregationView from './InsuranceAggregationView'
import InsuranceConstellationView from './InsuranceConstellationView'
import './InsurancePage.css'

const CARRIER_ID = 'acme_re'

function fmtSI(amount) {
  if (amount == null) return '—'
  if (amount >= 1e9) return `$${(amount / 1e9).toFixed(1)}B`
  if (amount >= 1e6) return `$${(amount / 1e6).toFixed(0)}M`
  return `$${amount.toLocaleString()}`
}

function fmtDate(isoStr) {
  if (!isoStr) return '—'
  return isoStr.slice(0, 10)
}

function fmtDateTime(isoStr) {
  if (!isoStr) return '—'
  return isoStr.slice(0, 16).replace('T', ' ') + ' UTC'
}

const BAND_COLORS = {
  low: '#15803d', moderate: '#0369a1', elevated: '#d97706', high: '#dc2626', critical: '#7f1d1d',
}
const SEV_COLORS = {
  low: '#6b7280', medium: '#d97706', high: '#dc2626', critical: '#7f1d1d',
}
const STATUS_COLORS = {
  operational: '#15803d', degraded: '#d97706', safe_mode: '#dc2626', decommissioned: '#6b7280',
}
const COV_COLORS = {
  continuous: '#15803d', good: '#0369a1', intermittent: '#d97706', gap: '#dc2626',
}

function Badge({ color, children }) {
  return (
    <span className="ins-badge" style={{ background: color + '18', color, borderColor: color + '40' }}>
      {children}
    </span>
  )
}

function KpiTile({ label, value, sub, color }) {
  return (
    <div className="ins-kpi-tile">
      <div className="ins-kpi-label">{label}</div>
      <div className="ins-kpi-value" style={color ? { color } : {}}>
        {value ?? '—'}
      </div>
      {sub && <div className="ins-kpi-sub">{sub}</div>}
    </div>
  )
}

function useApiData(url) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!url) return
    let cancelled = false
    setLoading(true)
    setData(null)
    setError(null)
    apiFetch(url)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch(e => { if (!cancelled) { setError(e.message); setLoading(false) } })
    return () => { cancelled = true }
  }, [url])

  return { data, loading, error }
}

function LoadingState({ message }) {
  return <div className="ins-loading">{message || 'Loading…'}</div>
}

function ErrorState({ error }) {
  return <div className="ins-error">Error loading data: {error}</div>
}

// ── BookDashboard ─────────────────────────────────────────────────────────────

function BookDashboard() {
  const { data, loading, error } = useApiData(API_ENDPOINTS.INSURANCE.DASHBOARD(CARRIER_ID))

  if (loading) return <LoadingState message="Loading dashboard…" />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  const s = data.summary
  const ar = s.active_risks || {}
  const oe = s.overnight_events || {}
  const cov = s.coverage || {}
  const renewals = s.renewals || {}
  const topShell = s.aggregation_watch?.[0]

  return (
    <div className="ins-section">
      <h2 className="ins-section-title">
        Book Dashboard
        <span className="ins-carrier-badge">Acme Re</span>
      </h2>

      <div className="ins-kpi-row">
        <KpiTile
          label="Active Assets"
          value={ar.count}
          sub={fmtSI(ar.total_sum_insured) + ' total SI'}
        />
        <KpiTile
          label="Overnight Events"
          value={oe.count}
          color={oe.count > 0 ? (SEV_COLORS[oe.max_severity] || '#dc2626') : undefined}
          sub={oe.count > 0 ? `Max severity: ${oe.max_severity}` : 'None active'}
        />
        <KpiTile
          label="Continuous Coverage"
          value={`${cov.pct_continuous ?? 0}%`}
          sub={`${cov.continuous_assets ?? 0} of ${cov.total_assets ?? 0} assets`}
          color="#0369a1"
        />
        <KpiTile
          label="Renewals <30d"
          value={renewals.d30?.count ?? 0}
          sub={`${renewals.d60?.count ?? 0} in 60d · ${renewals.d90?.count ?? 0} in 90d`}
        />
        <KpiTile
          label="Top Aggregation Shell"
          value={topShell?.label || '—'}
          sub={topShell ? `${fmtSI(topShell.sum_insured)} · ${topShell.pct_of_book}% of book` : ''}
        />
      </div>

      {oe.events?.length > 0 && (
        <div className="ins-card">
          <h3 className="ins-card-title">Active &amp; Overnight Events</h3>
          <table className="ins-table">
            <thead>
              <tr>
                <th>Event ID</th>
                <th>Type</th>
                <th>Severity</th>
                <th>Occurred (UTC)</th>
                <th>Sum at Risk</th>
                <th>Witnesses</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {oe.events.map(e => (
                <tr key={e.event_id}>
                  <td><code className="ins-code">{e.event_id}</code></td>
                  <td className="ins-capitalize">{e.type?.replace(/_/g, ' ')}</td>
                  <td><Badge color={SEV_COLORS[e.severity] || '#6b7280'}>{e.severity}</Badge></td>
                  <td>{fmtDateTime(e.occurred_at)}</td>
                  <td className="ins-bold">{fmtSI(e.total_sum_at_risk)}</td>
                  <td className="ins-center">{e.witness_count ?? '—'}</td>
                  <td className="ins-center">
                    {e.confidence != null ? `${(e.confidence * 100).toFixed(0)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {s.aggregation_watch?.length > 0 && (
        <div className="ins-card">
          <h3 className="ins-card-title">Aggregation Watch — Exposure Heatmap by Shell</h3>
          <ExposureHeatmap shells={s.aggregation_watch} />
          <table className="ins-table" style={{ marginTop: '0.75rem' }}>
            <thead>
              <tr>
                <th>Shell</th>
                <th>Sum Insured</th>
                <th>% of Book</th>
                <th>Assets</th>
              </tr>
            </thead>
            <tbody>
              {s.aggregation_watch.map(sh => (
                <tr key={sh.shell_id}>
                  <td>{sh.label || sh.shell_id}</td>
                  <td className="ins-bold">{fmtSI(sh.sum_insured)}</td>
                  <td>{sh.pct_of_book}%</td>
                  <td>{sh.asset_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── ExposureHeatmap ───────────────────────────────────────────────────────────

function ExposureHeatmap({ shells }) {
  if (!shells || shells.length === 0) return null
  const maxSI = Math.max(...shells.map(s => s.sum_insured || 0), 1)
  return (
    <div className="ins-heatmap">
      {shells.map(s => (
        <div key={s.shell_id} className="ins-heatmap-row">
          <div className="ins-heatmap-label" title={s.shell_id}>
            {s.label || s.shell_id?.replace(/_/g, ' ')}
          </div>
          <div className="ins-heatmap-track">
            <div
              className="ins-heatmap-fill"
              style={{ width: `${Math.round((s.sum_insured / maxSI) * 100)}%` }}
              title={fmtSI(s.sum_insured)}
            />
          </div>
          <div className="ins-heatmap-value">{fmtSI(s.sum_insured)}</div>
        </div>
      ))}
    </div>
  )
}

// ── AssetList ─────────────────────────────────────────────────────────────────

const SHELLS = ['LEO_500_520', 'LEO_520_540', 'LEO_540_560', 'LEO_560_580', 'MEO_19000_21000', 'GEO_W', 'GEO_E']
const RISK_BANDS = ['low', 'moderate', 'elevated', 'high', 'critical']
const PAGE_SIZE = 20

function AssetList({ onSelectAsset, onNavigateToCatalog, onNavigateToObservations }) {
  const [page, setPage] = useState(0)
  const [shell, setShell] = useState('')
  const [riskBand, setRiskBand] = useState('')

  const url = API_ENDPOINTS.INSURANCE.ASSETS(CARRIER_ID, page, PAGE_SIZE, shell, riskBand)
  const { data, loading, error } = useApiData(url)

  const assets = data?.assets || []
  const total = data?.total || 0

  return (
    <div className="ins-section">
      <h2 className="ins-section-title">
        Book of Business
        {total > 0 && <span className="ins-carrier-badge">{total} assets</span>}
      </h2>

      <div className="ins-filters">
        <select
          value={shell}
          onChange={e => { setShell(e.target.value); setPage(0) }}
          className="ins-select"
        >
          <option value="">All Shells</option>
          {SHELLS.map(s => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <select
          value={riskBand}
          onChange={e => { setRiskBand(e.target.value); setPage(0) }}
          className="ins-select"
        >
          <option value="">All Risk Bands</option>
          {RISK_BANDS.map(b => (
            <option key={b} value={b}>{b.charAt(0).toUpperCase() + b.slice(1)}</option>
          ))}
        </select>
      </div>

      {loading && <LoadingState message="Loading assets…" />}
      {error && <ErrorState error={error} />}

      {!loading && !error && (
        <div className="ins-card">
          <table className="ins-table ins-table-hover">
            <thead>
              <tr>
                <th>Asset</th>
                <th>NORAD</th>
                <th>Operator</th>
                <th>Shell</th>
                <th>Sum Insured</th>
                <th>Risk Band</th>
                <th>Risk Score</th>
                <th>Policy Expiry</th>
                {onNavigateToCatalog && <th></th>}
                {onNavigateToObservations && <th></th>}
              </tr>
            </thead>
            <tbody>
              {assets.map(a => (
                <tr
                  key={a.satellite_id}
                  className="ins-row-clickable"
                  onClick={() => onSelectAsset && onSelectAsset(a)}
                  title="Click to view asset detail"
                >
                  <td className="ins-bold ins-link-cell">{a.name || a.satellite_id}</td>
                  <td className="ins-muted">{a.norad_id}</td>
                  <td>{a.operator || '—'}</td>
                  <td className="ins-small">{a.shell_id?.replace(/_/g, ' ') || '—'}</td>
                  <td className="ins-bold">{fmtSI(a.sum_insured)}</td>
                  <td>
                    <Badge color={BAND_COLORS[a.risk_band] || '#6b7280'}>
                      {a.risk_band || '—'}
                    </Badge>
                  </td>
                  <td className="ins-center">{a.risk_score ?? '—'}</td>
                  <td className="ins-small">{fmtDate(a.policy_expiry)}</td>
                  {onNavigateToCatalog && (
                    <td>
                      <button
                        className="ins-btn ins-btn-link"
                        title="View in Object Catalog"
                        onClick={(e) => { e.stopPropagation(); onNavigateToCatalog(a) }}
                      >
                        ↗ Catalog
                      </button>
                    </td>
                  )}
                  {onNavigateToObservations && (
                    <td>
                      <button
                        className="ins-btn ins-btn-link"
                        title="View observations for this object"
                        onClick={(e) => { e.stopPropagation(); onNavigateToObservations(a) }}
                      >
                        ↗ Observations
                      </button>
                    </td>
                  )}
                </tr>
              ))}
              {assets.length === 0 && (
                <tr>
                  <td colSpan={8} className="ins-empty">No assets found</td>
                </tr>
              )}
            </tbody>
          </table>

          {total > PAGE_SIZE && (
            <div className="ins-pagination">
              <button
                className="ins-btn"
                onClick={() => setPage(p => p - 1)}
                disabled={page === 0}
              >
                Previous
              </button>
              <span>Page {page + 1} of {Math.ceil(total / PAGE_SIZE)}</span>
              <button
                className="ins-btn"
                onClick={() => setPage(p => p + 1)}
                disabled={(page + 1) * PAGE_SIZE >= total}
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── CoverageView ──────────────────────────────────────────────────────────────

function CoverageView() {
  const { data, loading, error } = useApiData(API_ENDPOINTS.INSURANCE.COVERAGE(CARRIER_ID))

  if (loading) return <LoadingState message="Loading coverage data…" />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  const bands = [
    { key: 'continuous', label: 'Continuous', pct: data.pct_continuous ?? 0 },
    { key: 'good', label: 'Good', pct: data.pct_good ?? 0 },
    { key: 'intermittent', label: 'Intermittent', pct: data.pct_intermittent ?? 0 },
    { key: 'gap', label: 'Gap Risk', pct: data.pct_gap ?? 0 },
  ]

  return (
    <div className="ins-section">
      <h2 className="ins-section-title">Aggregation &amp; Coverage</h2>

      <div className="ins-kpi-row">
        {bands.map(b => (
          <KpiTile key={b.key} label={b.label} value={`${b.pct}%`} color={COV_COLORS[b.key]} />
        ))}
      </div>

      <div className="ins-card">
        <h3 className="ins-card-title">Book-Level Coverage Distribution</h3>
        <div className="ins-coverage-bar">
          {bands.filter(b => b.pct > 0).map(b => (
            <div
              key={b.key}
              className="ins-coverage-segment"
              style={{ flex: b.pct, background: COV_COLORS[b.key] }}
              title={`${b.label}: ${b.pct}%`}
            >
              {b.pct > 8 ? `${b.label} ${b.pct}%` : ''}
            </div>
          ))}
        </div>
      </div>

      {data.weakest_assets?.length > 0 && (
        <div className="ins-card">
          <h3 className="ins-card-title">Weakest Assets by Coverage Windows</h3>
          <table className="ins-table">
            <thead>
              <tr>
                <th>Asset</th>
                <th>Shell</th>
                <th>Coverage Windows (24h)</th>
                <th>P95 Gap (min)</th>
                <th>Band</th>
              </tr>
            </thead>
            <tbody>
              {data.weakest_assets.map(a => (
                <tr key={a.satellite_id}>
                  <td className="ins-bold">{a.name || a.satellite_id}</td>
                  <td className="ins-small">{a.shell_id?.replace(/_/g, ' ') || '—'}</td>
                  <td className="ins-center">{a.cw_count}</td>
                  <td className="ins-center">{a.p95_gap_min}</td>
                  <td>
                    <Badge color={COV_COLORS[a.coverage_band] || '#6b7280'}>
                      {a.coverage_band || '—'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.weakest_shells?.length > 0 && (
        <div className="ins-card">
          <h3 className="ins-card-title">Weakest Shells by Average Revisit</h3>
          <table className="ins-table">
            <thead>
              <tr>
                <th>Shell</th>
                <th>Avg Revisit (min)</th>
              </tr>
            </thead>
            <tbody>
              {data.weakest_shells.map(s => (
                <tr key={s.shell_id}>
                  <td>{s.shell_id?.replace(/_/g, ' ') || '—'}</td>
                  <td className="ins-center">{s.avg_revisit_min}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── ConstellationView ─────────────────────────────────────────────────────────

function ConstellationView() {
  const { data, loading, error } = useApiData(API_ENDPOINTS.INSURANCE.CONSTELLATION)

  if (loading) return <LoadingState message="Loading constellation status…" />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  const { kestrels = [], health = {}, capacity = {} } = data

  return (
    <div className="ins-section">
      <h2 className="ins-section-title">
        Constellation &amp; Coverage
        <span className="ins-carrier-badge">{kestrels.length} Kestrels</span>
      </h2>

      <div className="ins-kpi-row">
        <KpiTile label="Operational" value={health.operational ?? 0} color="#15803d" />
        <KpiTile label="Degraded" value={health.degraded ?? 0} color="#d97706" />
        <KpiTile label="Safe Mode" value={health.safe_mode ?? 0} color="#dc2626" />
        <KpiTile label="Tasks in Queue" value={capacity.tasks_in_queue ?? 0} />
        <KpiTile
          label="Obs Completed 24h"
          value={(capacity.obs_completed_24h ?? 0).toLocaleString()}
          sub={`of ${(capacity.obs_scheduled_24h ?? 0).toLocaleString()} scheduled`}
        />
      </div>

      <div className="ins-kestrel-grid">
        {kestrels.map(k => (
          <div key={k.id} className="ins-kestrel-card">
            <div className="ins-kestrel-header">
              <span className="ins-kestrel-name">{k.name || k.id}</span>
              <Badge color={STATUS_COLORS[k.status] || '#6b7280'}>{k.status}</Badge>
            </div>
            <div className="ins-kestrel-detail">
              <div>
                <span className="ins-kd-label">Orbit</span>
                {k.orbit_summary?.regime || '—'} · {k.orbit_summary?.alt_km} km ·{' '}
                {k.orbit_summary?.inclination_deg}°
              </div>
              <div>
                <span className="ins-kd-label">Sensors</span>
                {k.sensor_types?.join(', ') || '—'}
              </div>
              <div>
                <span className="ins-kd-label">NORAD</span>
                {k.norad_id || '—'}
              </div>
              {k.next_window && (
                <div>
                  <span className="ins-kd-label">Next task</span>
                  {fmtDateTime(k.next_window)}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function InsurancePage({ activeSubTab, onNavigateToCatalog, onNavigateToObservations }) {
  const [selectedAsset, setSelectedAsset] = useState(null)

  const handleSelectAsset = (asset) => setSelectedAsset(asset)
  const handleBack = () => setSelectedAsset(null)

  if (activeSubTab === 'asset-detail') {
    if (selectedAsset) {
      return (
        <InsuredAssetDetail
          asset={selectedAsset}
          policy={{
            policy_id: selectedAsset.policy_id,
            sum_insured: selectedAsset.sum_insured,
            policy_expiry: selectedAsset.policy_expiry,
          }}
          onBack={handleBack}
          onNavigateToCatalog={onNavigateToCatalog}
          onNavigateToObservations={onNavigateToObservations}
        />
      )
    }
    return <AssetList onSelectAsset={handleSelectAsset} onNavigateToCatalog={onNavigateToCatalog} onNavigateToObservations={onNavigateToObservations} />
  }

  if (activeSubTab === 'book-dashboard') return <BookDashboard />
  if (activeSubTab === 'aggregation') return <InsuranceAggregationView />
  if (activeSubTab === 'constellation') return <InsuranceConstellationView />
  return null
}

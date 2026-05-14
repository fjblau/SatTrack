import { useState, useEffect } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import './InsurancePage.css'
import './InsuredAssetDetail.css'

const BAND_COLORS = {
  low: '#15803d', moderate: '#0369a1', elevated: '#d97706', high: '#dc2626', critical: '#7f1d1d',
}
const SEV_COLORS = {
  low: '#6b7280', medium: '#d97706', high: '#dc2626', critical: '#7f1d1d',
}
const COV_COLORS = {
  continuous: '#15803d', good: '#0369a1', intermittent: '#d97706', gap: '#dc2626',
}
const TASK_STATUS_COLORS = {
  scheduled: '#0369a1', executing: '#d97706', completed: '#15803d', failed: '#dc2626', cancelled: '#6b7280',
}

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

function fmtPct(val) {
  if (val == null) return '—'
  return `${(val * 100).toFixed(1)}%`
}

function Badge({ color, children }) {
  return (
    <span className="ins-badge" style={{ background: color + '18', color, borderColor: color + '40' }}>
      {children}
    </span>
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

function KpiTile({ label, value, sub, color }) {
  return (
    <div className="ins-kpi-tile">
      <div className="ins-kpi-label">{label}</div>
      <div className="ins-kpi-value" style={color ? { color } : {}}>{value ?? '—'}</div>
      {sub && <div className="ins-kpi-sub">{sub}</div>}
    </div>
  )
}

// ── Mini bar chart for risk score history ────────────────────────────────────

function RiskScoreChart({ history }) {
  if (!history || history.length === 0) return <div className="iad-no-data">No history available</div>

  const maxScore = Math.max(...history.map(h => Math.max(h.talon_score || 0, h.baseline_score || 0, 1)))

  return (
    <div className="iad-chart">
      <div className="iad-chart-bars">
        {history.map((h, i) => (
          <div key={i} className="iad-chart-col">
            <div className="iad-chart-bar-pair">
              {h.talon_score != null && (
                <div
                  className="iad-bar iad-bar-talon"
                  style={{ height: `${Math.round((h.talon_score / maxScore) * 100)}%` }}
                  title={`TALON: ${h.talon_score}`}
                />
              )}
              {h.baseline_score != null && (
                <div
                  className="iad-bar iad-bar-baseline"
                  style={{ height: `${Math.round((h.baseline_score / maxScore) * 100)}%` }}
                  title={`Baseline: ${h.baseline_score}`}
                />
              )}
            </div>
            <div className="iad-chart-label">{h.month?.slice(5)}</div>
          </div>
        ))}
      </div>
      <div className="iad-chart-legend">
        <span className="iad-legend-item"><span className="iad-legend-dot iad-bar-talon" />TALON</span>
        <span className="iad-legend-item"><span className="iad-legend-dot iad-bar-baseline" />Telemetry-only baseline</span>
      </div>
    </div>
  )
}

// ── Horizon gauge ─────────────────────────────────────────────────────────────

function ProbabilityGauge({ label, talon, baseline, delta }) {
  const tPct = talon != null ? Math.round(talon * 100) : 0
  const bPct = baseline != null ? Math.round(baseline * 100) : 0
  const deltaSign = delta > 0 ? '+' : ''

  return (
    <div className="iad-gauge">
      <div className="iad-gauge-label">{label}</div>
      <div className="iad-gauge-track">
        <div className="iad-gauge-fill iad-gauge-talon" style={{ width: `${tPct}%` }} title={`TALON: ${tPct}%`} />
      </div>
      <div className="iad-gauge-track iad-gauge-track-thin">
        <div className="iad-gauge-fill iad-gauge-baseline" style={{ width: `${bPct}%` }} title={`Baseline: ${bPct}%`} />
      </div>
      <div className="iad-gauge-values">
        <span className="iad-gauge-val iad-gauge-talon-val">{tPct}% TALON</span>
        <span className="iad-gauge-sep">vs</span>
        <span className="iad-gauge-val iad-gauge-base-val">{bPct}% baseline</span>
        {delta != null && (
          <span className="iad-gauge-delta" style={{ color: delta > 0 ? '#dc2626' : '#15803d' }}>
            {deltaSign}{Math.round(delta * 100)}pp
          </span>
        )}
      </div>
    </div>
  )
}

// ── Exposure bar chart (horizontal) ──────────────────────────────────────────

function ExposureHeatmap({ shells }) {
  if (!shells || shells.length === 0) return <div className="iad-no-data">No shell data</div>
  const maxSI = Math.max(...shells.map(s => s.sum_insured || 0), 1)
  return (
    <div className="iad-heatmap">
      {shells.map(s => (
        <div key={s.shell_id} className="iad-heatmap-row">
          <div className="iad-heatmap-label" title={s.shell_id}>{s.label || s.shell_id?.replace(/_/g, ' ')}</div>
          <div className="iad-heatmap-bar-track">
            <div
              className="iad-heatmap-bar"
              style={{ width: `${Math.round((s.sum_insured / maxSI) * 100)}%` }}
              title={fmtSI(s.sum_insured)}
            />
          </div>
          <div className="iad-heatmap-value">{fmtSI(s.sum_insured)}</div>
          <div className="iad-heatmap-count">{s.asset_count} assets</div>
        </div>
      ))}
    </div>
  )
}

// ── Tab: Insurance Overview ───────────────────────────────────────────────────

function OverviewTab({ asset, policy }) {
  return (
    <div className="iad-tab-content">
      <div className="ins-kpi-row">
        <KpiTile label="Sum Insured" value={fmtSI(policy?.sum_insured)} sub={`Policy ${policy?.policy_id}`} />
        <KpiTile label="Policy Expiry" value={fmtDate(policy?.policy_expiry)} />
        <KpiTile
          label="Risk Band"
          value={<Badge color={BAND_COLORS[asset?.risk_band] || '#6b7280'}>{asset?.risk_band || '—'}</Badge>}
        />
        <KpiTile label="Risk Score" value={asset?.risk_score} color={BAND_COLORS[asset?.risk_band]} />
        <KpiTile label="Shell" value={asset?.shell_id?.replace(/_/g, ' ') || '—'} />
      </div>

      <div className="ins-card">
        <h3 className="ins-card-title">Asset Information</h3>
        <table className="ins-table">
          <tbody>
            <tr><td className="iad-field-label">Name</td><td className="ins-bold">{asset?.name || asset?.satellite_id}</td></tr>
            <tr><td className="iad-field-label">NORAD ID</td><td>{asset?.norad_id || '—'}</td></tr>
            <tr><td className="iad-field-label">Operator</td><td>{asset?.operator || '—'}</td></tr>
            <tr><td className="iad-field-label">Satellite ID</td><td><code className="ins-code">{asset?.satellite_id}</code></td></tr>
            <tr><td className="iad-field-label">Coverage Band</td><td>
              <Badge color={COV_COLORS[asset?.coverage_band] || '#6b7280'}>{asset?.coverage_band || '—'}</Badge>
            </td></tr>
            <tr><td className="iad-field-label">Currency</td><td>{asset?.currency || 'USD'}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Tab: Risk Score ───────────────────────────────────────────────────────────

function RiskScoreTab({ satelliteId }) {
  const { data, loading, error } = useApiData(API_ENDPOINTS.INSURANCE.ASSET_RISK_SCORE(satelliteId))

  if (loading) return <LoadingState message="Loading risk score…" />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  const latest = data.latest || {}
  const comps = latest.components || {}

  return (
    <div className="iad-tab-content">
      <div className="ins-kpi-row">
        <KpiTile
          label="TALON Score"
          value={latest.score}
          color={BAND_COLORS[latest.score_band] || '#6b7280'}
          sub={<Badge color={BAND_COLORS[latest.score_band] || '#6b7280'}>{latest.score_band}</Badge>}
        />
        <KpiTile label="Baseline Score" value={latest.baseline_score} sub="Telemetry-only" />
        <KpiTile
          label="Delta"
          value={latest.delta != null ? (latest.delta > 0 ? `+${latest.delta}` : latest.delta) : '—'}
          color={latest.delta > 0 ? '#dc2626' : '#15803d'}
          sub="TALON vs baseline"
        />
        <KpiTile label="Computed" value={fmtDate(latest.computed_at)} />
      </div>

      <div className="ins-card">
        <h3 className="ins-card-title">7-Month Risk Score History — TALON vs Telemetry Baseline</h3>
        <RiskScoreChart history={data.monthly_history} />
      </div>

      {Object.keys(comps).length > 0 && (
        <div className="ins-card">
          <h3 className="ins-card-title">Score Components</h3>
          <table className="ins-table">
            <thead>
              <tr><th>Component</th><th>Value</th></tr>
            </thead>
            <tbody>
              {Object.entries(comps).map(([k, v]) => (
                <tr key={k}>
                  <td>{k.replace(/_/g, ' ')}</td>
                  <td className="ins-center">{typeof v === 'number' ? v.toFixed(3) : String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Tab: Prediction ───────────────────────────────────────────────────────────

function PredictionTab({ satelliteId }) {
  const { data, loading, error } = useApiData(API_ENDPOINTS.INSURANCE.ASSET_PREDICTION(satelliteId))

  if (loading) return <LoadingState message="Loading predictions…" />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  const horizons = data.horizons || {}

  return (
    <div className="iad-tab-content">
      <div className="ins-card">
        <h3 className="ins-card-title">
          Anomaly Prediction Horizons
          <span className="iad-model-tag">{data.model_version}</span>
          <span className="iad-model-tag">{fmtDateTime(data.generated_at)}</span>
        </h3>

        <div className="iad-gauges">
          {Object.entries(horizons).map(([horizon, h]) => (
            <ProbabilityGauge
              key={horizon}
              label={`${horizon} horizon`}
              talon={h.talon_probability}
              baseline={h.baseline_probability}
              delta={h.delta}
            />
          ))}
        </div>
      </div>

      <div className="ins-kpi-row">
        {Object.entries(horizons).map(([horizon, h]) => (
          <KpiTile
            key={horizon}
            label={`${horizon} driver`}
            value={h.primary_driver?.replace(/_/g, ' ') || '—'}
            sub={`Confidence: ${fmtPct(h.confidence)}`}
          />
        ))}
      </div>

      {data.primary_factors?.length > 0 && (
        <div className="ins-card">
          <h3 className="ins-card-title">Primary Risk Factors</h3>
          <ul className="iad-list">
            {data.primary_factors.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}

      {data.recommended_actions?.length > 0 && (
        <div className="ins-card">
          <h3 className="ins-card-title">Recommended Actions</h3>
          <ul className="iad-list">
            {data.recommended_actions.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Tab: Coverage ─────────────────────────────────────────────────────────────

function CoverageTab({ satelliteId }) {
  const { data, loading, error } = useApiData(API_ENDPOINTS.INSURANCE.ASSET_COVERAGE(satelliteId))

  if (loading) return <LoadingState message="Loading coverage detail…" />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  const s = data.summary || {}

  return (
    <div className="iad-tab-content">
      <div className="ins-kpi-row">
        <KpiTile
          label="Coverage Band"
          value={<Badge color={COV_COLORS[s.coverage_band] || '#6b7280'}>{s.coverage_band}</Badge>}
        />
        <KpiTile label="Median Revisit" value={`${s.median_revisit_min ?? '—'} min`} />
        <KpiTile label="P95 Gap" value={`${s.p95_gap_min ?? '—'} min`} color={s.p95_gap_min > 60 ? '#dc2626' : undefined} />
        <KpiTile label="Sensors" value={s.sensor_diversity_count ?? 0} sub={s.sensor_diversity?.join(', ') || '—'} />
        <KpiTile label="Windows (48h)" value={s.window_count_48h ?? 0} />
        <KpiTile label="Obs (30d)" value={s.obs_count_30d ?? 0} />
      </div>

      {data.kestrels?.length > 0 && (
        <div className="ins-card">
          <h3 className="ins-card-title">Assigned Kestrels</h3>
          <div className="iad-kestrel-chips">
            {data.kestrels.map(k => (
              <span key={k.id} className="iad-kestrel-chip">
                {k.name || k.id}
                <span className="iad-chip-sensors">{k.sensor_types?.join(' · ') || '—'}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {data.upcoming_windows?.length > 0 && (
        <div className="ins-card">
          <h3 className="ins-card-title">Upcoming Observation Windows (48h)</h3>
          <table className="ins-table">
            <thead>
              <tr>
                <th>Kestrel</th>
                <th>Window Start (UTC)</th>
                <th>Window End (UTC)</th>
                <th>Duration (s)</th>
                <th>Max Elevation</th>
                <th>Geo Quality</th>
              </tr>
            </thead>
            <tbody>
              {data.upcoming_windows.map((w, i) => (
                <tr key={i}>
                  <td><code className="ins-code">{w.kestrel_id}</code></td>
                  <td>{fmtDateTime(w.start)}</td>
                  <td>{fmtDateTime(w.end)}</td>
                  <td className="ins-center">{w.duration_s ?? '—'}</td>
                  <td className="ins-center">{w.max_elevation_deg != null ? `${w.max_elevation_deg}°` : '—'}</td>
                  <td className="ins-center">{w.geometry_quality ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.observation_history?.length > 0 && (
        <div className="ins-card">
          <h3 className="ins-card-title">Observation History (30 days)</h3>
          <table className="ins-table">
            <thead>
              <tr>
                <th>Observed At (UTC)</th>
                <th>Kestrel</th>
                <th>Geo Quality</th>
                <th>Anomaly Score</th>
                <th>Observation ID</th>
              </tr>
            </thead>
            <tbody>
              {data.observation_history.map((o, i) => (
                <tr key={i}>
                  <td>{fmtDateTime(o.observed_at)}</td>
                  <td>{o.kestrel_id || '—'}</td>
                  <td className="ins-center">{o.geometry_quality ?? '—'}</td>
                  <td className="ins-center">{o.anomaly_score != null ? o.anomaly_score.toFixed(3) : '—'}</td>
                  <td><code className="ins-code ins-small">{o.observation_id}</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Tab: Events / Witness Chain ───────────────────────────────────────────────

function EventsTab({ satelliteId }) {
  const { data, loading, error } = useApiData(
    `${API_ENDPOINTS.INSURANCE.EVENTS()}${satelliteId ? `&satellite_id=${encodeURIComponent(satelliteId)}` : ''}`
  )
  const [selectedEvent, setSelectedEvent] = useState(null)
  const { data: witnessData, loading: witnessLoading } = useApiData(
    selectedEvent ? API_ENDPOINTS.INSURANCE.EVENT_WITNESSES(selectedEvent) : null
  )

  if (loading) return <LoadingState message="Loading events…" />
  if (error) return <ErrorState error={error} />

  const events = data?.events || []

  return (
    <div className="iad-tab-content">
      <div className="ins-card">
        <h3 className="ins-card-title">Loss Events</h3>
        {events.length === 0 ? (
          <div className="ins-empty">No loss events found</div>
        ) : (
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
                <th>Witness Chain</th>
              </tr>
            </thead>
            <tbody>
              {events.map(e => (
                <tr key={e.event_id} className={selectedEvent === e.event_id ? 'iad-row-selected' : ''}>
                  <td><code className="ins-code">{e.event_id}</code></td>
                  <td className="ins-capitalize">{e.type?.replace(/_/g, ' ')}</td>
                  <td><Badge color={SEV_COLORS[e.severity] || '#6b7280'}>{e.severity}</Badge></td>
                  <td>{fmtDateTime(e.occurred_at)}</td>
                  <td className="ins-bold">{fmtSI(e.total_sum_at_risk)}</td>
                  <td className="ins-center">{e.witness_count ?? '—'}</td>
                  <td className="ins-center">{e.confidence != null ? `${(e.confidence * 100).toFixed(0)}%` : '—'}</td>
                  <td>
                    <button className="iad-link-btn" onClick={() => setSelectedEvent(
                      selectedEvent === e.event_id ? null : e.event_id
                    )}>
                      {selectedEvent === e.event_id ? 'Hide' : 'View'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selectedEvent && (
        <div className="ins-card">
          <h3 className="ins-card-title">Witness Chain — {selectedEvent}</h3>
          {witnessLoading ? <LoadingState message="Loading witnesses…" /> : (
            witnessData && (
              <>
                <div className="ins-kpi-row">
                  <KpiTile
                    label="Confidence"
                    value={witnessData.confidence != null ? `${(witnessData.confidence * 100).toFixed(0)}%` : '—'}
                    color="#0369a1"
                  />
                  <KpiTile label="Confirmation Latency" value={
                    witnessData.confirmation_latency_s != null ? `${witnessData.confirmation_latency_s}s` : '—'
                  } />
                  <KpiTile label="Fusion Group" value={witnessData.fusion_group_id} />
                </div>
                <table className="ins-table">
                  <thead>
                    <tr>
                      <th>Kestrel</th>
                      <th>Name</th>
                      <th>Observed At</th>
                      <th>Geo Quality</th>
                      <th>Independence</th>
                      <th>Sensors</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(witnessData.witnesses || []).map(w => (
                      <tr key={w.kestrel_id}>
                        <td><code className="ins-code">{w.kestrel_id}</code></td>
                        <td>{w.name}</td>
                        <td>{fmtDateTime(w.observed_at)}</td>
                        <td className="ins-center">{w.geometry_quality ?? '—'}</td>
                        <td className="ins-center">{w.independence_score}</td>
                        <td>{w.sensor_types?.join(', ') || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {witnessData.evidence_package?.package_hash && (
                  <div className="iad-hash-block">
                    <span className="iad-hash-label">Evidence Package Hash:</span>
                    <code className="ins-code">{witnessData.evidence_package.package_hash}</code>
                  </div>
                )}
              </>
            )
          )}
        </div>
      )}
    </div>
  )
}

// ── Tab: Tasking ──────────────────────────────────────────────────────────────

function TaskingTab({ satelliteId }) {
  const { data, loading, error } = useApiData(API_ENDPOINTS.INSURANCE.ASSET_TASKING(satelliteId))

  if (loading) return <LoadingState message="Loading task queue…" />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  const tasks = data.tasks || []
  const summary = data.queue_summary || {}

  return (
    <div className="iad-tab-content">
      <div className="ins-kpi-row">
        {Object.entries(summary).map(([status, count]) => (
          <KpiTile
            key={status}
            label={status.charAt(0).toUpperCase() + status.slice(1)}
            value={count}
            color={TASK_STATUS_COLORS[status]}
          />
        ))}
      </div>

      <div className="ins-card">
        <h3 className="ins-card-title">Task Queue</h3>
        {tasks.length === 0 ? (
          <div className="ins-empty">No tasks found for this asset</div>
        ) : (
          <table className="ins-table">
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Kestrel</th>
                <th>Type</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Scheduled For (UTC)</th>
                <th>Completed At (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map(t => (
                <tr key={t.task_id}>
                  <td><code className="ins-code ins-small">{t.task_id}</code></td>
                  <td>{t.kestrel_name || t.kestrel_id}</td>
                  <td className="ins-capitalize">{t.task_type?.replace(/_/g, ' ') || '—'}</td>
                  <td>
                    <Badge color={TASK_STATUS_COLORS[t.status] || '#6b7280'}>{t.status}</Badge>
                  </td>
                  <td className="ins-center">{t.priority ?? '—'}</td>
                  <td>{fmtDateTime(t.scheduled_for)}</td>
                  <td>{fmtDateTime(t.completed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── Tab: Provenance ───────────────────────────────────────────────────────────

function ProvenanceTab({ satelliteId }) {
  const { data, loading, error } = useApiData(`/v2/provenance/objects/${encodeURIComponent(satelliteId)}/chain`)

  if (loading) return <LoadingState message="Loading provenance chain…" />
  if (error) return (
    <div className="iad-tab-content">
      <div className="ins-card">
        <div className="ins-empty">Provenance chain not available for this asset ({error})</div>
      </div>
    </div>
  )
  if (!data) return null

  return (
    <div className="iad-tab-content">
      <div className="ins-card">
        <h3 className="ins-card-title">Provenance Chain</h3>
        <pre className="iad-json-pre">{JSON.stringify(data, null, 2)}</pre>
      </div>
    </div>
  )
}

// ── Tab: Documents ────────────────────────────────────────────────────────────

function DocumentsTab({ satelliteId, policy }) {
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState(null)

  const handleExport = async (lossEventId) => {
    setExporting(true)
    setExportError(null)
    try {
      const res = await apiFetch(API_ENDPOINTS.INSURANCE.EXPORT_EVIDENCE(lossEventId), { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `talon_evidence_${lossEventId}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setExportError(e.message)
    } finally {
      setExporting(false)
    }
  }

  const { data: eventsData } = useApiData(API_ENDPOINTS.INSURANCE.EVENTS())
  const events = eventsData?.events || []

  return (
    <div className="iad-tab-content">
      <div className="ins-card">
        <h3 className="ins-card-title">Registration Documents</h3>
        <div className="ins-empty">
          Registration documents are available via the Satellite Catalog — Provenance tab.
        </div>
      </div>

      <div className="ins-card">
        <h3 className="ins-card-title">Evidence Package Export</h3>
        <p className="iad-desc">
          Download a PDF evidence package for any loss event. The package includes the full witness chain,
          cryptographic custody hashes, and compliance summary.
        </p>
        {exportError && <div className="ins-error">Export failed: {exportError}</div>}
        {events.length === 0 ? (
          <div className="ins-empty">No loss events available for export</div>
        ) : (
          <table className="ins-table">
            <thead>
              <tr>
                <th>Event ID</th>
                <th>Type</th>
                <th>Severity</th>
                <th>Occurred</th>
                <th>Export PDF</th>
              </tr>
            </thead>
            <tbody>
              {events.slice(0, 10).map(e => (
                <tr key={e.event_id}>
                  <td><code className="ins-code">{e.event_id}</code></td>
                  <td className="ins-capitalize">{e.type?.replace(/_/g, ' ')}</td>
                  <td><Badge color={SEV_COLORS[e.severity] || '#6b7280'}>{e.severity}</Badge></td>
                  <td>{fmtDate(e.occurred_at)}</td>
                  <td>
                    <button
                      className="iad-export-btn"
                      disabled={exporting}
                      onClick={() => handleExport(e.event_id)}
                    >
                      {exporting ? 'Exporting…' : '↓ PDF'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

const TABS = [
  { id: 'overview', label: 'Insurance Overview' },
  { id: 'risk-score', label: 'Risk Score' },
  { id: 'prediction', label: 'Prediction' },
  { id: 'coverage', label: 'Coverage' },
  { id: 'events', label: 'Events / Witness Chain' },
  { id: 'tasking', label: 'Tasking' },
  { id: 'provenance', label: 'Provenance' },
  { id: 'documents', label: 'Documents' },
]

export default function InsuredAssetDetail({ asset, policy, onBack, onNavigateToCatalog, onNavigateToObservations }) {
  const [activeTab, setActiveTab] = useState('overview')
  const satelliteId = asset?.satellite_id

  return (
    <div className="iad-wrapper">
      <div className="iad-header">
        <div className="iad-header-actions">
          <button className="iad-back-btn" onClick={onBack}>← Back to Book</button>
          {onNavigateToCatalog && (
            <button
              className="iad-back-btn"
              onClick={() => onNavigateToCatalog(asset)}
              title="View this object in the Object Catalog"
            >
              ↗ View in Catalog
            </button>
          )}
          {onNavigateToObservations && asset?.norad_id && (
            <button
              className="iad-back-btn"
              onClick={() => onNavigateToObservations(asset)}
              title="View observations for this object in the Observation Dashboard"
            >
              ↗ View Observations
            </button>
          )}
        </div>
        <div className="iad-title-block">
          <h2 className="iad-title">{asset?.name || satelliteId}</h2>
          <div className="iad-subtitle">
            <code className="ins-code">{satelliteId}</code>
            {asset?.norad_id && <span> · NORAD {asset.norad_id}</span>}
            {asset?.operator && <span> · {asset.operator}</span>}
            {asset?.risk_band && (
              <Badge color={BAND_COLORS[asset.risk_band] || '#6b7280'}>{asset.risk_band}</Badge>
            )}
          </div>
        </div>
      </div>

      <nav className="iad-tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`iad-tab-btn${activeTab === t.id ? ' active' : ''}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {activeTab === 'overview' && <OverviewTab asset={asset} policy={policy} />}
      {activeTab === 'risk-score' && <RiskScoreTab satelliteId={satelliteId} />}
      {activeTab === 'prediction' && <PredictionTab satelliteId={satelliteId} />}
      {activeTab === 'coverage' && <CoverageTab satelliteId={satelliteId} />}
      {activeTab === 'events' && <EventsTab satelliteId={satelliteId} />}
      {activeTab === 'tasking' && <TaskingTab satelliteId={satelliteId} />}
      {activeTab === 'provenance' && <ProvenanceTab satelliteId={satelliteId} />}
      {activeTab === 'documents' && <DocumentsTab satelliteId={satelliteId} policy={policy} />}
    </div>
  )
}

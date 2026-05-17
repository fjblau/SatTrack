import { useState, useEffect, useCallback } from 'react'
import apiFetch from '../utils/apiFetch'
import './CustomerTasksPage.css'

const INTERNAL_STATUSES = [
  'drafted', 'submitted', 'accepted', 'executing', 'paused',
  'completed', 'delivered', 'disputed', 'closed', 'cancelled',
  'pending_review', 'qa_review', 'loss_assessment', 'escalated',
]

const PAGE_SIZE = 25

function fmtDate(isoStr) {
  if (!isoStr) return '—'
  return isoStr.slice(0, 10)
}

function fmtDateTime(isoStr) {
  if (!isoStr) return '—'
  return isoStr.slice(0, 16).replace('T', ' ') + ' UTC'
}

function noradFromId(id) {
  if (!id) return '—'
  const parts = id.split('/')
  return parts[parts.length - 1]
}

function partyFromId(id) {
  if (!id) return '—'
  const parts = id.split('/')
  return parts[parts.length - 1]
}

function statusBadgeClass(status) {
  if (!status) return 'ct-badge ct-badge-unknown'
  const key = status.toLowerCase().replace(/\s+/g, '_')
  return `ct-badge ct-badge-${key}`
}

function StatusBadge({ status }) {
  return <span className={statusBadgeClass(status)}>{status || '—'}</span>
}

function PriorityBadge({ priority }) {
  const cls = priority === 'urgent' ? 'ct-badge ct-priority-urgent' : 'ct-badge ct-priority-routine'
  return <span className={cls}>{priority || '—'}</span>
}

function SeverityBadge({ severity }) {
  const cls = `ct-badge ct-sev-${severity || 'low'}`
  return <span className={cls}>{severity || '—'}</span>
}

function LoadingState({ message }) {
  return <div className="ct-loading">{message || 'Loading…'}</div>
}

function ErrorState({ error }) {
  return <div className="ct-error">Error loading data: {error}</div>
}

function TransitionModal({ taskKey, toStatus, onClose, onSuccess }) {
  const [actor, setActor] = useState('talon_operator')
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const handleConfirm = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const res = await apiFetch(`/v2/customer-tasks/${taskKey}/transition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to_status: toStatus,
          actor,
          actor_type: 'operator',
          note,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      onSuccess()
    } catch (e) {
      setError(e.message)
      setSubmitting(false)
    }
  }

  return (
    <div className="ct-modal-overlay" onClick={onClose}>
      <div className="ct-modal" onClick={e => e.stopPropagation()}>
        <div className="ct-modal-title">Transition → {toStatus}</div>
        {error && <div className="ct-error">{error}</div>}
        <div className="ct-modal-field">
          <label>Actor</label>
          <input value={actor} onChange={e => setActor(e.target.value)} />
        </div>
        <div className="ct-modal-field">
          <label>Note</label>
          <textarea value={note} onChange={e => setNote(e.target.value)} placeholder="Optional note…" />
        </div>
        <div className="ct-modal-actions">
          <button className="ct-btn" onClick={onClose} disabled={submitting}>Cancel</button>
          <button className="ct-btn ct-btn-primary" onClick={handleConfirm} disabled={submitting}>
            {submitting ? 'Confirming…' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  )
}

function TaskDetail({ taskKey, onBack }) {
  const [task, setTask] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [modalState, setModalState] = useState(null)

  const fetchDetail = useCallback(() => {
    setLoading(true)
    setError(null)
    apiFetch(`/v2/customer-tasks/${taskKey}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { setTask(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [taskKey])

  useEffect(() => { fetchDetail() }, [fetchDetail])

  if (loading) return <LoadingState message="Loading task…" />
  if (error) return (
    <div className="ct-section">
      <button className="ct-btn ct-btn-sm" onClick={onBack}>← Back to list</button>
      <ErrorState error={error} />
    </div>
  )
  if (!task) return null

  const sla = task.sla || {}
  const scope = task.scope || {}
  const commercial = task.commercial || (task.quote ? { fee_amount: task.quote.amount_usd, currency: 'USD' } : {})
  const deliveryDue = sla.delivery_due
  const isOverdue = deliveryDue && new Date(deliveryDue) < new Date()
  const obsMin = scope.observation_count_min
  const obsMax = scope.observation_count_max
  const obsCount = task.observation_count ?? 0
  const metMin = obsMin != null && obsCount >= obsMin
  const passes = task.passes || []
  const deliverables = task.deliverables || []
  const transitions = task.recent_transitions || []
  const activeAlerts = task.active_alerts || []
  const allowedNext = task.allowed_next_states || []

  return (
    <div className="ct-section">
      <div className="ct-detail-header">
        <button className="ct-btn ct-btn-sm" onClick={onBack}>← Back to list</button>
        <span className="ct-detail-task-number">{task.task_number || task._key}</span>
        <StatusBadge status={task.customer_status} />
        <PriorityBadge priority={task.priority} />
      </div>

      <div className="ct-card">
        <div className="ct-card-title">Scope</div>
        <div className="ct-detail-grid">
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">Time Window Start</span>
            <span className="ct-detail-field-value">{fmtDateTime(scope.time_window_start)}</span>
          </div>
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">Time Window End</span>
            <span className="ct-detail-field-value">{fmtDateTime(scope.time_window_end)}</span>
          </div>
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">Observation Count Min</span>
            <span className="ct-detail-field-value">{obsMin ?? '—'}</span>
          </div>
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">Observation Count Max</span>
            <span className="ct-detail-field-value">{obsMax ?? '—'}</span>
          </div>
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">Required Sensor Types</span>
            <span className="ct-detail-field-value">
              {scope.required_sensor_types?.join(', ') || '—'}
            </span>
          </div>
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">Maneuver Authorised</span>
            <span className="ct-detail-field-value">
              {scope.maneuver_authorised != null ? (scope.maneuver_authorised ? 'Yes' : 'No') : '—'}
            </span>
          </div>
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">Min Independence Score</span>
            <span className="ct-detail-field-value">{scope.min_independence_score ?? '—'}</span>
          </div>
        </div>
      </div>

      <div className="ct-card">
        <div className="ct-card-title">Commercial</div>
        <div className="ct-detail-grid">
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">Fee</span>
            <span className="ct-detail-field-value">
              {commercial.fee_amount != null
                ? `${commercial.fee_amount} ${commercial.currency || ''}`.trim()
                : '—'}
            </span>
          </div>
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">Billing</span>
            <span className="ct-detail-field-value">{commercial.billing || '—'}</span>
          </div>
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">PO Reference</span>
            <span className="ct-detail-field-value">{commercial.po_reference || '—'}</span>
          </div>
        </div>
      </div>

      <div className="ct-card">
        <div className="ct-card-title">SLA</div>
        <div className="ct-detail-grid">
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">Delivery Due</span>
            <span className={`ct-detail-field-value ${isOverdue ? 'ct-overdue' : ''}`}>
              {fmtDate(deliveryDue)}{isOverdue ? ' ⚠ overdue' : ''}
            </span>
          </div>
          <div className="ct-detail-field">
            <span className="ct-detail-field-label">QA Window (days)</span>
            <span className="ct-detail-field-value">{sla.qa_window_days ?? '—'}</span>
          </div>
        </div>
      </div>

      <div className="ct-card">
        <div className="ct-card-title">Observation Summary</div>
        <div className="ct-obs-summary">
          <span className={metMin ? 'ct-check-ok' : 'ct-check-no'}>
            {metMin ? '✓' : '✗'}
          </span>
          <span>
            <strong>{obsCount}</strong> observations
            {obsMin != null && ` (promised ${obsMin}–${obsMax ?? '∞'})`}
          </span>
        </div>
      </div>

      {passes.length > 0 && (
        <div className="ct-card">
          <div className="ct-card-title">Per-Pass Breakdown</div>
          <table className="ct-table">
            <thead>
              <tr>
                <th>Pass ID</th>
                <th>Kestrel ID</th>
                <th>First Epoch</th>
                <th>Last Epoch</th>
                <th>Frames</th>
                <th>Sunlit</th>
              </tr>
            </thead>
            <tbody>
              {passes.map((p, i) => (
                <tr key={p.pass_id || i}>
                  <td><code className="ct-code">{p.pass_id || '—'}</code></td>
                  <td className="ct-muted">{p.kestrel_id || '—'}</td>
                  <td className="ct-small">{fmtDateTime(p.first_epoch)}</td>
                  <td className="ct-small">{fmtDateTime(p.last_epoch)}</td>
                  <td className="ct-bold">{p.frame_count ?? '—'}</td>
                  <td>{p.sunlit_frames ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {deliverables.length > 0 && (
        <div className="ct-card">
          <div className="ct-card-title">Deliverables</div>
          <table className="ct-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Version</th>
                <th>Produced At</th>
                <th>Released To Customer</th>
              </tr>
            </thead>
            <tbody>
              {deliverables.map((d, i) => (
                <tr key={d._key || i}>
                  <td>{d.type || '—'}</td>
                  <td className="ct-muted">{d.version || '—'}</td>
                  <td className="ct-small">{fmtDateTime(d.produced_at)}</td>
                  <td>{d.released_to_customer ? 'Yes' : 'No'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="ct-card">
        <div className="ct-card-title">Audit Log</div>
        {transitions.length === 0
          ? <div className="ct-muted">No transitions recorded.</div>
          : (
            <div className="ct-timeline">
              {transitions.map((tr, i) => (
                <div key={tr._key || i} className="ct-timeline-item">
                  <div className="ct-timeline-dot" />
                  <div className="ct-timeline-content">
                    <div className="ct-timeline-transition">
                      {tr.from_status || '—'} → {tr.to_status || '—'}
                    </div>
                    <div className="ct-timeline-meta">
                      {fmtDateTime(tr.occurred_at)}
                      {tr.actor && ` · ${tr.actor}`}
                    </div>
                    {tr.note && <div className="ct-timeline-note">{tr.note}</div>}
                  </div>
                </div>
              ))}
            </div>
          )
        }
      </div>

      {activeAlerts.length > 0 && (
        <div className="ct-card">
          <div className="ct-card-title">Active Alerts</div>
          {activeAlerts.map((a, i) => (
            <div key={a._key || i} className="ct-alert-row">
              <span className="ct-alert-icon">⚠</span>
              <span className="ct-alert-type">{a.alert_type || '—'}</span>
              <SeverityBadge severity={a.severity} />
              <span className="ct-alert-meta">{fmtDateTime(a.triggered_at)}</span>
            </div>
          ))}
        </div>
      )}

      {allowedNext.length > 0 && (
        <div className="ct-card">
          <div className="ct-card-title">Allowed Next States</div>
          <div className="ct-next-states">
            {allowedNext.map(s => (
              <button
                key={s}
                className="ct-btn"
                onClick={() => setModalState(s)}
              >
                → {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {modalState && (
        <TransitionModal
          taskKey={taskKey}
          toStatus={modalState}
          onClose={() => setModalState(null)}
          onSuccess={() => { setModalState(null); fetchDetail() }}
        />
      )}
    </div>
  )
}

function AlertsFeed() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch('/v2/customer-tasks/alerts?status=active')
      .then(r => r.json())
      .then(d => { setAlerts(Array.isArray(d) ? d : []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="ct-loading" style={{ padding: '1rem' }}>Loading alerts…</div>
  if (alerts.length === 0) return <div className="ct-muted" style={{ padding: '0.5rem 0' }}>No active alerts.</div>

  return (
    <div>
      {alerts.map((a, i) => (
        <div key={a._key || i} className="ct-alert-row">
          <span className="ct-alert-icon">⚠</span>
          <span className="ct-alert-type">{a.alert_type || '—'}</span>
          <SeverityBadge severity={a.severity} />
          <span className="ct-alert-meta">{a.task_id}</span>
          <span className="ct-alert-meta">{fmtDateTime(a.triggered_at)}</span>
        </div>
      ))}
    </div>
  )
}

function CustomerTasksPage() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedTaskKey, setSelectedTaskKey] = useState(null)
  const [page, setPage] = useState(0)

  const [filterCarrier, setFilterCarrier] = useState('')
  const [filterStatuses, setFilterStatuses] = useState([])
  const [filterPriority, setFilterPriority] = useState('')

  const [appliedCarrier, setAppliedCarrier] = useState('')
  const [appliedStatuses, setAppliedStatuses] = useState([])
  const [appliedPriority, setAppliedPriority] = useState('')

  const fetchTasks = useCallback((pageNum, carrier, statuses, priority) => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams()
    params.append('limit', PAGE_SIZE)
    params.append('offset', pageNum * PAGE_SIZE)
    if (carrier) params.append('carrier_id', carrier)
    statuses.forEach(s => params.append('status', s))
    if (priority) params.append('priority', priority)

    apiFetch(`/v2/customer-tasks?${params}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { setTasks(Array.isArray(d) ? d : []); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  useEffect(() => {
    fetchTasks(0, '', [], '')
  }, [fetchTasks])

  const handleApply = () => {
    setAppliedCarrier(filterCarrier)
    setAppliedStatuses(filterStatuses)
    setAppliedPriority(filterPriority)
    setPage(0)
    fetchTasks(0, filterCarrier, filterStatuses, filterPriority)
  }

  const handlePageChange = (newPage) => {
    setPage(newPage)
    fetchTasks(newPage, appliedCarrier, appliedStatuses, appliedPriority)
  }

  const handleStatusMultiSelect = (e) => {
    const selected = Array.from(e.target.selectedOptions).map(o => o.value)
    setFilterStatuses(selected)
  }

  if (selectedTaskKey) {
    return (
      <div className="analytics-view-container">
        <TaskDetail taskKey={selectedTaskKey} onBack={() => setSelectedTaskKey(null)} />
      </div>
    )
  }

  return (
    <div className="analytics-view-container">
      <div className="ct-section">
        <h2 className="ct-section-title">Customer Tasks</h2>

        <div className="ct-filters">
          <div className="ct-filter-group">
            <span className="ct-filter-label">Carrier ID</span>
            <input
              className="ct-input"
              value={filterCarrier}
              onChange={e => setFilterCarrier(e.target.value)}
              placeholder="e.g. acme_re"
            />
          </div>
          <div className="ct-filter-group">
            <span className="ct-filter-label">Status</span>
            <select
              multiple
              className="ct-select-multi"
              value={filterStatuses}
              onChange={handleStatusMultiSelect}
            >
              {INTERNAL_STATUSES.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="ct-filter-group">
            <span className="ct-filter-label">Priority</span>
            <select
              className="ct-select"
              value={filterPriority}
              onChange={e => setFilterPriority(e.target.value)}
            >
              <option value="">All</option>
              <option value="routine">Routine</option>
              <option value="urgent">Urgent</option>
            </select>
          </div>
          <div className="ct-filter-group" style={{ justifyContent: 'flex-end' }}>
            <button className="ct-btn ct-btn-primary" onClick={handleApply}>Apply</button>
          </div>
        </div>

        {loading && <LoadingState message="Loading tasks…" />}
        {error && <ErrorState error={error} />}

        {!loading && !error && (
          <div className="ct-card">
            <table className="ct-table">
              <thead>
                <tr>
                  <th>Task #</th>
                  <th>Customer Status</th>
                  <th>Target</th>
                  <th>Priority</th>
                  <th>Delivery Due</th>
                  <th>Carrier</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {tasks.map(t => (
                  <tr key={t._key}>
                    <td className="ct-bold">{t.task_number || t._key}</td>
                    <td><StatusBadge status={t.customer_status} /></td>
                    <td className="ct-code">{noradFromId(t.target_object_id)}</td>
                    <td>
                      {t.priority === 'urgent'
                        ? <span className="ct-priority-urgent-text">urgent</span>
                        : t.priority || '—'}
                    </td>
                    <td className="ct-small">{fmtDate(t.delivery_due)}</td>
                    <td className="ct-muted">{partyFromId(t.requesting_party_id)}</td>
                    <td>
                      <button
                        className="ct-btn ct-btn-link"
                        onClick={() => setSelectedTaskKey(t._key)}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
                {tasks.length === 0 && (
                  <tr>
                    <td colSpan={7} className="ct-empty">No tasks found</td>
                  </tr>
                )}
              </tbody>
            </table>

            <div className="ct-pagination">
              <button
                className="ct-btn"
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 0}
              >
                Previous
              </button>
              <span>Page {page + 1}</span>
              <button
                className="ct-btn"
                onClick={() => handlePageChange(page + 1)}
                disabled={tasks.length < PAGE_SIZE}
              >
                Next
              </button>
            </div>
          </div>
        )}

        <div className="ct-alerts-feed">
          <h3 className="ct-card-title" style={{ marginBottom: '0.5rem' }}>Active SLA Alerts</h3>
          <AlertsFeed />
        </div>
      </div>
    </div>
  )
}

export default CustomerTasksPage

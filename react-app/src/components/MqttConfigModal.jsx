import { useState, useEffect } from 'react'
import './MqttConfigModal.css'

export default function MqttConfigModal({ satellite, tleData, onClose }) {
  const [config, setConfig] = useState({
    broker_host: '',
    broker_port: 1883,
    username: '',
    password: '',
    topic: '',
    frequency_hours: 24,
    enabled: true
  })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [testing, setTesting] = useState(false)
  const [hasExistingConfig, setHasExistingConfig] = useState(false)

  useEffect(() => {
    if (!satellite?._mongodb_id) return

    const fetchConfig = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await fetch(`/v2/mqtt/config/${encodeURIComponent(satellite._mongodb_id)}`)
        if (response.ok) {
          const data = await response.json()
          if (data.data) {
            const broker = data.data.mqtt_broker || {}
            setConfig({
              broker_host: broker.host || '',
              broker_port: broker.port || 1883,
              username: broker.username || '',
              password: '',
              topic: data.data.topic || '',
              frequency_hours: data.data.frequency_hours || 24,
              enabled: data.data.enabled !== false
            })
            setHasExistingConfig(true)
          }
        }
      } catch (err) {
        console.error('Error fetching MQTT config:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchConfig()
  }, [satellite?._mongodb_id])

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose()
    }
    
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  const handleChange = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }))
    setError(null)
    setSuccess(null)
  }

  const validateForm = () => {
    if (!config.broker_host.trim()) {
      setError('Broker host is required')
      return false
    }
    if (config.broker_port < 1 || config.broker_port > 65535) {
      setError('Broker port must be between 1 and 65535')
      return false
    }
    if (!config.topic.trim()) {
      setError('Topic is required')
      return false
    }
    if (![8, 24].includes(config.frequency_hours)) {
      setError('Frequency must be 8 or 24 hours')
      return false
    }
    return true
  }

  const handleSave = async () => {
    if (!validateForm()) return

    setSaving(true)
    setError(null)
    setSuccess(null)

    try {
      const payload = {
        satellite_id: satellite._mongodb_id,
        norad_id: satellite._norad_id,
        satellite_name: satellite['Object Name'],
        mqtt_broker: {
          host: config.broker_host.trim(),
          port: parseInt(config.broker_port),
          username: config.username.trim() || null,
          password: config.password.trim() || null
        },
        topic: config.topic.trim(),
        frequency_hours: parseInt(config.frequency_hours),
        enabled: config.enabled
      }

      const response = await fetch('/v2/mqtt/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.message || 'Failed to save configuration')
      }

      const result = await response.json()
      setSuccess('Configuration saved successfully!')
      setHasExistingConfig(true)
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err.message || 'Failed to save configuration')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!hasExistingConfig) return
    if (!confirm('Are you sure you want to delete this MQTT configuration?')) return

    setSaving(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await fetch(`/v2/mqtt/config/${encodeURIComponent(satellite._mongodb_id)}`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.message || 'Failed to delete configuration')
      }

      setSuccess('Configuration deleted successfully!')
      setHasExistingConfig(false)
      setConfig({
        broker_host: '',
        broker_port: 1883,
        username: '',
        password: '',
        topic: '',
        frequency_hours: 24,
        enabled: true
      })
      setTimeout(() => setSuccess(null), 2000)
    } catch (err) {
      setError(err.message || 'Failed to delete configuration')
    } finally {
      setSaving(false)
    }
  }

  const handleTestConnection = async () => {
    if (!config.broker_host.trim()) {
      setError('Please enter broker host first')
      return
    }

    setTesting(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await fetch('/v2/mqtt/test-connection', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          broker_host: config.broker_host.trim(),
          broker_port: parseInt(config.broker_port),
          username: config.username.trim() || null,
          password: config.password.trim() || null
        })
      })

      const result = await response.json()
      
      if (result.success) {
        setSuccess('Connection test successful!')
        setTimeout(() => setSuccess(null), 3000)
      } else {
        setError(result.message || 'Connection test failed')
      }
    } catch (err) {
      setError('Connection test failed: ' + err.message)
    } finally {
      setTesting(false)
    }
  }

  const handlePublishNow = async () => {
    if (!hasExistingConfig) {
      setError('Please save configuration first')
      return
    }

    setSaving(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await fetch(`/v2/mqtt/publish-now/${encodeURIComponent(satellite._mongodb_id)}`, {
        method: 'POST'
      })

      const result = await response.json()
      
      if (result.success) {
        setSuccess('TLE published successfully!')
        setTimeout(() => setSuccess(null), 3000)
      } else {
        setError(result.message || 'Failed to publish TLE')
      }
    } catch (err) {
      setError('Failed to publish: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!satellite) return null

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-content mqtt-modal">
        <div className="modal-header">
          <div>
            <h2>MQTT Feed Configuration</h2>
            <p className="modal-subtitle">{satellite['Object Name']}</p>
          </div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <div className="modal-body">
          {loading ? (
            <div className="loading-message">Loading configuration...</div>
          ) : (
            <div className="mqtt-form">
              {error && (
                <div className="message error-message">{error}</div>
              )}
              {success && (
                <div className="message success-message">{success}</div>
              )}

              <div className="form-section">
                <h3>Broker Configuration</h3>
                
                <div className="form-group">
                  <label htmlFor="broker_host">Broker Host *</label>
                  <input
                    id="broker_host"
                    type="text"
                    placeholder="mqtt.example.com"
                    value={config.broker_host}
                    onChange={(e) => handleChange('broker_host', e.target.value)}
                    disabled={saving || testing}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="broker_port">Broker Port *</label>
                  <input
                    id="broker_port"
                    type="number"
                    min="1"
                    max="65535"
                    value={config.broker_port}
                    onChange={(e) => handleChange('broker_port', e.target.value)}
                    disabled={saving || testing}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="username">Username</label>
                  <input
                    id="username"
                    type="text"
                    placeholder="Optional"
                    value={config.username}
                    onChange={(e) => handleChange('username', e.target.value)}
                    disabled={saving || testing}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="password">Password</label>
                  <input
                    id="password"
                    type="password"
                    placeholder={hasExistingConfig ? "Leave empty to keep current" : "Optional"}
                    value={config.password}
                    onChange={(e) => handleChange('password', e.target.value)}
                    disabled={saving || testing}
                  />
                </div>

                <button 
                  className="test-button"
                  onClick={handleTestConnection}
                  disabled={saving || testing || !config.broker_host}
                >
                  {testing ? 'Testing...' : 'Test Connection'}
                </button>
              </div>

              <div className="form-section">
                <h3>Publishing Configuration</h3>
                
                <div className="form-group">
                  <label htmlFor="topic">MQTT Topic *</label>
                  <input
                    id="topic"
                    type="text"
                    placeholder="satellites/tle/{norad_id}"
                    value={config.topic}
                    onChange={(e) => handleChange('topic', e.target.value)}
                    disabled={saving || testing}
                  />
                  <small>Use {'{norad_id}'} as placeholder for NORAD ID</small>
                </div>

                <div className="form-group">
                  <label htmlFor="frequency">Publishing Frequency *</label>
                  <select
                    id="frequency"
                    value={config.frequency_hours}
                    onChange={(e) => handleChange('frequency_hours', parseInt(e.target.value))}
                    disabled={saving || testing}
                  >
                    <option value={8}>Every 8 hours</option>
                    <option value={24}>Every 24 hours</option>
                  </select>
                </div>

                <div className="form-group checkbox-group">
                  <label>
                    <input
                      type="checkbox"
                      checked={config.enabled}
                      onChange={(e) => handleChange('enabled', e.target.checked)}
                      disabled={saving || testing}
                    />
                    <span>Enable automatic publishing</span>
                  </label>
                </div>
              </div>

              {tleData && !tleData._notFound && (
                <div className="tle-preview">
                  <h3>Current TLE Data</h3>
                  <div className="tle-lines">
                    {tleData.line1 && <code>{tleData.line1}</code>}
                    {tleData.line2 && <code>{tleData.line2}</code>}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
        
        <div className="modal-footer">
          <div className="footer-left">
            {hasExistingConfig && (
              <>
                <button 
                  className="modal-button publish-button"
                  onClick={handlePublishNow}
                  disabled={saving || testing}
                >
                  {saving ? 'Publishing...' : 'Publish Now'}
                </button>
                <button 
                  className="modal-button delete-button"
                  onClick={handleDelete}
                  disabled={saving || testing}
                >
                  Delete
                </button>
              </>
            )}
          </div>
          <div className="footer-right">
            <button 
              className="modal-button save-button"
              onClick={handleSave}
              disabled={saving || testing}
            >
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
            <button 
              className="modal-button close-button"
              onClick={onClose}
              disabled={saving || testing}
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

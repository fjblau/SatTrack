import { useEffect } from 'react'
import './DataRecordModal.css'

export default function DataRecordModal({ data, onClose }) {
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

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
      alert('Copied to clipboard!')
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  if (!data) return null

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-content">
        <div className="modal-header">
          <h2>MongoDB Document</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <div className="modal-body">
          <pre className="json-display">
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
        
        <div className="modal-footer">
          <button className="modal-button copy-button" onClick={handleCopy}>
            Copy to Clipboard
          </button>
          <button className="modal-button close-button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

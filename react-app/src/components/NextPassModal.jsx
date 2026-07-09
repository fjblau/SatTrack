import { useEffect } from 'react'
import NextPassContent from './NextPassContent'
import './NextPassModal.css'

export default function NextPassModal({ satellite, noradId, onClose }) {
  const satelliteName = satellite?.canonical?.name || satellite?.['Object Name'] || `NORAD ${noradId}`

  useEffect(() => {
    const handleEscape = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-content next-pass-modal">
        <div className="modal-header">
          <div>
            <h2>Next Pass</h2>
            <p className="modal-subtitle">{satelliteName}</p>
          </div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <NextPassContent resolvedTarget={{ type: 'norad', noradId, name: satelliteName }} />
      </div>
    </div>
  )
}

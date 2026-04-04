import { useEffect, useMemo, useState } from 'react'
import { triggerAutoFlow } from '../services/api'
import './TriggerPopup.css'

const DEFAULT_AUTO_LOCATION = {
  lat: 13.0827,
  lng: 80.2707,
}

function TriggerPopup({
  isOpen,
  disruption = 'Heavy Rain',
  policy = 'HeatGuard',
  eligiblePayout = 'INR 8,000',
  triggerType = 'unknown',
  claimContext,
  onClose,
  onClaimSuccess,
  onClaimError,
}) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState('')

  const normalizedTriggerType = String(triggerType || 'unknown')
    .replaceAll('_', ' ')
    .trim()
    .toLowerCase()
  const triggerTypeLabel = normalizedTriggerType
    ? normalizedTriggerType.charAt(0).toUpperCase() + normalizedTriggerType.slice(1)
    : 'Unknown'

  const detectedAtLabel = useMemo(() => {
    const rawTimestamp = claimContext?.timestamp
    if (!rawTimestamp) {
      return 'Just now'
    }

    const parsed = new Date(rawTimestamp)
    if (Number.isNaN(parsed.getTime())) {
      return 'Just now'
    }

    return parsed.toLocaleString([], {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }, [claimContext])

  const locationLabel = useMemo(() => {
    const rawLocation = claimContext?.user_location
    const lat = Number(rawLocation?.lat)
    const lng = Number(rawLocation?.lng)

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return 'Using current route coordinates'
    }

    return `${lat.toFixed(4)}, ${lng.toFixed(4)}`
  }, [claimContext])

  useEffect(() => {
    if (!isOpen) {
      return undefined
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const onEscape = (event) => {
      if (event.key !== 'Escape' || isSubmitting) {
        return
      }

      setFeedback('')
      setError('')

      if (typeof onClose === 'function') {
        onClose()
      }
    }

    window.addEventListener('keydown', onEscape)

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', onEscape)
    }
  }, [isOpen, isSubmitting, onClose])

  const handleClose = () => {
    if (isSubmitting) {
      return
    }

    setFeedback('')
    setError('')

    if (typeof onClose === 'function') {
      onClose()
    }
  }

  const handleClaimNow = async () => {
    setIsSubmitting(true)
    setFeedback('')
    setError('')

    const claimLocation =
      claimContext && typeof claimContext === 'object' && claimContext.user_location
        ? claimContext.user_location
        : DEFAULT_AUTO_LOCATION
    const claimTimestamp =
      claimContext && typeof claimContext === 'object' && claimContext.timestamp
        ? claimContext.timestamp
        : new Date().toISOString()

    try {
      const response = await triggerAutoFlow({
        user_location: claimLocation,
        timestamp: claimTimestamp,
      })

      const responseData = response?.data || {}
      const status = String(responseData.status || '').toLowerCase()

      if (status === 'approved') {
        setFeedback('Auto-claim approved successfully.')
      } else if (status === 'verification_required') {
        setFeedback('Verification required before payout.')
      } else if (status === 'rejected') {
        setError(String(responseData.reason || 'Auto-claim was rejected.'))
      } else {
        setFeedback('Claim submitted. We will keep you updated on the next step.')
      }

      if (typeof onClaimSuccess === 'function') {
        onClaimSuccess(responseData)
      }
    } catch (claimError) {
      const responseDetail = claimError?.response?.data?.detail
      const normalizedDetail =
        typeof responseDetail === 'string' ? responseDetail : JSON.stringify(responseDetail)
      const message =
        normalizedDetail ||
        claimError?.response?.data?.message ||
        'Unable to submit auto-claim right now. Please try again.'

      setError(message)

      if (typeof onClaimError === 'function') {
        onClaimError(message)
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) {
    return null
  }

  return (
    <div
      className="trigger-popup-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="trigger-popup-title"
      onClick={handleClose}
    >
      <div className="trigger-popup-card" onClick={(event) => event.stopPropagation()}>
        <div className="trigger-popup-accent" />
        <p className="trigger-popup-kicker">
          <span className="trigger-popup-live-dot" aria-hidden="true" />
          Real-time disruption alert
        </p>
        <h2 id="trigger-popup-title" className="trigger-popup-title">
          Trigger detected near your route
        </h2>
        <p className="trigger-popup-subtitle">
          You are covered. Review the detected condition and submit your claim instantly.
        </p>

        <dl className="trigger-popup-meta-grid">
          <div className="trigger-popup-metric">
            <dt>Disruption</dt>
            <dd>{disruption}</dd>
          </div>
          <div className="trigger-popup-metric">
            <dt>Trigger type</dt>
            <dd>{triggerTypeLabel}</dd>
          </div>
          <div className="trigger-popup-metric">
            <dt>Policy match</dt>
            <dd>{policy}</dd>
          </div>
          <div className="trigger-popup-metric">
            <dt>Eligible payout</dt>
            <dd>{eligiblePayout}</dd>
          </div>
        </dl>

        <div className="trigger-popup-context">
          <p>
            <span>Detected at</span>
            <strong>{detectedAtLabel}</strong>
          </p>
          <p>
            <span>Coordinates</span>
            <strong>{locationLabel}</strong>
          </p>
        </div>

        {feedback ? <p className="trigger-popup-feedback">{feedback}</p> : null}
        {error ? <p className="trigger-popup-error">{error}</p> : null}

        <div className="trigger-popup-actions">
          <button
            type="button"
            className="trigger-popup-claim-btn"
            onClick={handleClaimNow}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Submitting claim...' : 'Claim now'}
          </button>
          <button
            type="button"
            className="trigger-popup-close-btn"
            onClick={handleClose}
            disabled={isSubmitting}
          >
            Dismiss
          </button>
        </div>

        <p className="trigger-popup-footnote">This alert is generated from live location and environmental signals.</p>
      </div>
    </div>
  )
}

export default TriggerPopup
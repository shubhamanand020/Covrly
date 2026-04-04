import { useLocation, useNavigate } from 'react-router-dom'
import './Payout.css'

const getStatusConfig = (status) => {
  if (status === 'approved') {
    return {
      label: 'Approved',
      suffix: '✅',
      className: 'payout-status-approved',
    }
  }

  if (status === 'verification_required') {
    return {
      label: 'Verification Required',
      suffix: '',
      className: 'payout-status-verification',
    }
  }

  if (status === 'rejected') {
    return {
      label: 'Rejected',
      suffix: '',
      className: 'payout-status-rejected',
    }
  }

  return {
    label: 'Unknown',
    suffix: '',
    className: 'payout-status-unknown',
  }
}

const formatRupees = (value) => {
  const amount = Number(value)
  if (!Number.isFinite(amount)) {
    return '₹0'
  }

  return `₹${amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

function Payout() {
  const navigate = useNavigate()
  const location = useLocation()

  const stateData =
    location?.state && typeof location.state === 'object' && !Array.isArray(location.state)
      ? location.state
      : null

  const isFlowEnvelope = stateData && typeof stateData.data === 'object' && stateData.status
  const status = String((isFlowEnvelope ? stateData.status : stateData?.status) || '').trim().toLowerCase()
  const details = isFlowEnvelope ? stateData.data : stateData

  if (!status) {
    return (
      <section className="payout-page">
        <article className="payout-card payout-card-empty">
          <h1>Payout Result</h1>
          <p className="payout-empty-text">No claim data found</p>
          <button
            type="button"
            className="payout-dashboard-button"
            onClick={() => navigate('/dashboard')}
          >
            Go Back to Dashboard
          </button>
        </article>
      </section>
    )
  }

  const statusConfig = getStatusConfig(status)
  const triggerDetected = Boolean(details?.trigger_detected)
  const payoutAmount = Number(details?.payout || 0)
  const reason = String(details?.reason || '')

  return (
    <section className="payout-page">
      <article className="payout-card" aria-label="Payout summary">
        <header className="payout-header">
          <h1>Payout Result</h1>
        </header>

        <div className={`payout-status ${statusConfig.className}`}>
          <strong>
            Status: {statusConfig.label}
            {statusConfig.suffix ? ` ${statusConfig.suffix}` : ''}
          </strong>
        </div>

        <div className="payout-details">
          <p>
            <span className="payout-details-label">Claim Status</span>
            <strong>{statusConfig.label}</strong>
          </p>
          <p>
            <span className="payout-details-label">Trigger Detected</span>
            <strong>{triggerDetected ? 'Yes' : 'No'}</strong>
          </p>
          <p>
            <span className="payout-details-label">Payout Amount</span>
            <strong>{status === 'approved' ? formatRupees(payoutAmount) : '₹0'}</strong>
          </p>
          {reason ? (
            <p>
              <span className="payout-details-label">Reason</span>
              <strong>{reason}</strong>
            </p>
          ) : null}
        </div>

        {status === 'approved' ? (
          <p className="payout-message payout-message-approved">Payout credited successfully.</p>
        ) : null}

        {status === 'rejected' ? (
          <p className="payout-message payout-message-error">No payout available</p>
        ) : null}

        {status === 'verification_required' ? (
          <p className="payout-message payout-message-info">
            Verification required before payout
          </p>
        ) : null}

        <button
          type="button"
          className="payout-dashboard-button"
          onClick={() => navigate('/dashboard')}
        >
          Go Back to Dashboard
        </button>
      </article>
    </section>
  )
}

export default Payout

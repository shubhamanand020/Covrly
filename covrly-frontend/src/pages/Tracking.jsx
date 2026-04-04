import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMyTriggers } from '../services/api'
import './Tracking.css'

const formatTriggerType = (value) => {
  const normalized = String(value || 'unknown')
    .trim()
    .replaceAll('_', ' ')
    .toLowerCase()
  if (!normalized) {
    return 'Unknown'
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

const formatTimestamp = (value) => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return 'Unknown time'
  }

  return parsed.toLocaleString([], {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const formatLocation = (trigger) => {
  const lat = Number(trigger?.location?.lat)
  const lng = Number(trigger?.location?.lng)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return 'Unknown location'
  }
  return `${lat.toFixed(4)}, ${lng.toFixed(4)}`
}

function Tracking() {
  const navigate = useNavigate()
  const [triggers, setTriggers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let isMounted = true

    const loadMyTriggers = async () => {
      setLoading(true)
      setError('')

      try {
        const response = await getMyTriggers()
        const items = Array.isArray(response?.data?.data?.triggers) ? response.data.data.triggers : []
        if (!isMounted) {
          return
        }
        setTriggers(items)
      } catch (requestError) {
        const detail = requestError?.response?.data?.detail
        if (isMounted) {
          setError(typeof detail === 'string' ? detail : 'Unable to load trigger history right now.')
        }
      } finally {
        if (isMounted) {
          setLoading(false)
        }
      }
    }

    loadMyTriggers()

    return () => {
      isMounted = false
    }
  }, [])

  const latestTrigger = useMemo(() => (triggers.length ? triggers[0] : null), [triggers])

  return (
    <section className="tracking-page">
      <header className="tracking-header">
        <h1>My Triggers</h1>
        <p>Review your latest disruption signals and claim readiness in one place.</p>
      </header>

      {loading ? <p className="tracking-status">Loading trigger history...</p> : null}
      {error ? <p className="tracking-status tracking-status-error">{error}</p> : null}

      <article className="tracking-card" aria-label="Tracking details">
        <div className="tracking-section">
          <span className="tracking-label">Latest trigger location</span>
          <p className="tracking-location">
            {latestTrigger ? formatLocation(latestTrigger) : 'No trigger location yet'}
          </p>
        </div>

        <div className="tracking-section">
          <span className="tracking-label">Recent triggers</span>
          {triggers.length ? (
            <ul className="tracking-trigger-list">
              {triggers.slice(0, 6).map((trigger, index) => (
                <li
                  key={
                    String(trigger.trigger_id || '').trim() ||
                    `${String(trigger.timestamp || '')}-${String(trigger.trigger_type || '')}-${index}`
                  }
                  className="tracking-trigger-chip"
                >
                  <strong>{formatTriggerType(trigger.trigger_type)}</strong>
                  <span>{formatTimestamp(trigger.timestamp)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="tracking-empty">No triggers detected yet.</p>
          )}
        </div>

        <div className="tracking-section tracking-section-highlight">
          <span className="tracking-label">Total stored triggers</span>
          <p className="tracking-payout">{triggers.length}</p>
        </div>

        <button
          type="button"
          className="tracking-payout-button"
          onClick={() => navigate('/payout')}
          disabled={!latestTrigger}
        >
          {latestTrigger ? 'Proceed to payout' : 'Payout unavailable'}
        </button>
      </article>
    </section>
  )
}

export default Tracking
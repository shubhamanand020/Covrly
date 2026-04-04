import { useMemo } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import './LocationPage.css'

const permissionLabelByState = {
  checking: 'Checking permission',
  prompt: 'Permission required',
  granted: 'Permission Granted',
  denied: 'Permission Denied',
  unsupported: 'Location Unsupported',
}

const permissionToneByState = {
  checking: 'is-warning',
  prompt: 'is-warning',
  granted: 'is-success',
  denied: 'is-danger',
  unsupported: 'is-danger',
}

const monitoringLabelByState = {
  idle: 'Waiting for first GPS fix',
  watching: 'Listening to live location',
  sending: 'Syncing to backend',
  synced: 'Monitoring Active',
  blocked: 'Blocked by permission',
  error: 'Monitoring interrupted',
}

const formatTimestamp = (value) => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return ''
  }

  return parsed.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function LocationPage() {
  const navigate = useNavigate()
  const context = useOutletContext() || {}

  const permissionState = String(context.permissionState || 'checking').toLowerCase()
  const monitorState = String(context.monitorState || 'idle').toLowerCase()
  const monitorHint = String(context.monitorHint || '')
  const formattedSyncTime = String(context.formattedSyncTime || '')
  const latestPosition = context.latestPosition && typeof context.latestPosition === 'object'
    ? context.latestPosition
    : null
  const lastDetectedTrigger = context.lastDetectedTrigger && typeof context.lastDetectedTrigger === 'object'
    ? context.lastDetectedTrigger
    : null
  const requestLocationPermission =
    typeof context.requestLocationPermission === 'function' ? context.requestLocationPermission : () => {}

  const permissionLabel = permissionLabelByState[permissionState] || 'Unknown permission state'
  const permissionTone = permissionToneByState[permissionState] || 'is-warning'
  const monitoringLabel = monitoringLabelByState[monitorState] || 'Monitoring status unavailable'

  const actionLabel =
    permissionState === 'granted'
      ? 'Sync Now'
      : permissionState === 'unsupported'
        ? 'Location Unsupported'
        : 'Enable Location'
  const actionDisabled = permissionState === 'unsupported'

  const coordinateLabel = useMemo(() => {
    const lat = Number(latestPosition?.lat)
    const lng = Number(latestPosition?.lng)
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return 'No location captured yet'
    }

    return `${lat.toFixed(5)}, ${lng.toFixed(5)}`
  }, [latestPosition])

  const triggerLabel = useMemo(() => {
    if (!lastDetectedTrigger) {
      return 'No trigger detected yet'
    }

    const triggerType = String(lastDetectedTrigger.triggerType || 'unknown').replaceAll('_', ' ')
    const normalizedTrigger = triggerType.charAt(0).toUpperCase() + triggerType.slice(1)
    const triggerTime = formatTimestamp(lastDetectedTrigger.timestamp)

    return triggerTime ? `${normalizedTrigger} at ${triggerTime}` : normalizedTrigger
  }, [lastDetectedTrigger])

  return (
    <section className="location-page">
      <header className="location-header">
        <h1>Location Services</h1>
        <p>Manage permissions and monitor live sync status from one place.</p>
      </header>

      <article className="location-card" aria-label="Location status and monitoring">
        <div className="location-card-group">
          <span className="location-kicker">Status</span>
          <p className={`location-status-pill ${permissionTone}`}>
            <span className="location-status-dot" aria-hidden="true" />
            {permissionLabel}
          </p>
        </div>

        <div className="location-card-group">
          <span className="location-kicker">Monitoring</span>
          <p className="location-monitor-label">
            {monitoringLabel}
            {formattedSyncTime ? ` (Last sync: ${formattedSyncTime})` : ''}
          </p>
          {monitorHint ? <p className="location-monitor-hint">{monitorHint}</p> : null}
        </div>

        <button
          type="button"
          className="location-sync-button"
          onClick={requestLocationPermission}
          disabled={actionDisabled}
        >
          {actionLabel}
        </button>
      </article>

      <article className="location-card" aria-label="Live location data">
        <h2>Live Data</h2>

        <div className="location-data-row">
          <span>Current lat/lng</span>
          <strong>{coordinateLabel}</strong>
        </div>

        <div className="location-data-row">
          <span>Last trigger detected</span>
          <strong>{triggerLabel}</strong>
        </div>

        <div className="location-actions-inline">
          <button type="button" className="location-secondary-button" onClick={() => navigate('/tracking')}>
            View Trigger Logs
          </button>
        </div>
      </article>
    </section>
  )
}

export default LocationPage

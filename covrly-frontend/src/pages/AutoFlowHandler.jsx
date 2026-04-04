import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { triggerAutoFlow } from '../services/api'
import './AutoFlowHandler.css'

const DEFAULT_AUTO_PAYLOAD = {
  user_location: {
    lat: 12.97,
    lng: 77.59,
  },
}

function AutoFlowHandler() {
  const navigate = useNavigate()
  const [statusText, setStatusText] = useState('Listening for trigger...')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const runAutoFlow = useCallback(async () => {
    setLoading(true)
    setError('')
    setStatusText('Checking for active trigger...')

    try {
      const response = await triggerAutoFlow({
        ...DEFAULT_AUTO_PAYLOAD,
        timestamp: new Date().toISOString(),
      })
      const flowResponse = response?.data || {}
      const status = String(flowResponse.status || '').toLowerCase()
      const nextStep = String(flowResponse.next_step || '').toLowerCase()

      if (status === 'approved' && nextStep === 'payout') {
        navigate('/payout', { state: flowResponse })
        return
      }

      if (status === 'verification_required' && nextStep === 'verify') {
        navigate('/verification', { state: flowResponse })
        return
      }

      const reason = flowResponse?.data?.reason
      setStatusText(typeof reason === 'string' ? reason : 'No active trigger right now.')
    } catch (requestError) {
      const detail = requestError?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Unable to run auto flow right now.')
    } finally {
      setLoading(false)
    }
  }, [navigate])

  useEffect(() => {
    runAutoFlow()
  }, [runAutoFlow])

  return (
    <section className="auto-flow-page">
      <article className="auto-flow-card">
        <h1>Triggers</h1>
        <p className="auto-flow-text">{statusText}</p>

        {error ? <p className="auto-flow-error">{error}</p> : null}

        <div className="auto-flow-actions">
          <button type="button" className="auto-flow-button" onClick={runAutoFlow} disabled={loading}>
            {loading ? 'Checking...' : 'Retry Trigger Check'}
          </button>
          <button type="button" className="auto-flow-button secondary" onClick={() => navigate('/dashboard')}>
            Back to Dashboard
          </button>
        </div>
      </article>
    </section>
  )
}

export default AutoFlowHandler

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PolicyCard from '../components/PolicyCard'
import { buyPolicy } from '../services/api'
import './Plans.css'

const resolveCurrentLocation = () =>
  new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      resolve(null)
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          lat: Number(position.coords.latitude),
          lng: Number(position.coords.longitude),
        })
      },
      () => resolve(null),
      {
        enableHighAccuracy: true,
        timeout: 5000,
        maximumAge: 60000,
      },
    )
  })

const featuredPolicies = [
  {
    name: 'HeatGuard',
    coverageItems: ['Heatwave emergency payout', 'Cooling device damage', 'Power outage support'],
    premium: '₹275/week',
    maxCoverageAmount: 'Rs 5,00,000',
  },
  {
    name: 'RainSure Cover',
    coverageItems: ['Flooded home support', 'Rain-related vehicle loss', 'Emergency shelter allowance'],
    premium: '₹210/week',
    maxCoverageAmount: 'Rs 4,00,000',
  },
  {
    name: 'CivicShield Cover',
    coverageItems: ['Riot disruption claims', 'Public service outage aid', 'Urban mobility interruption'],
    premium: '₹240/week',
    maxCoverageAmount: 'Rs 4,50,000',
  },
  {
    name: 'Holistic Cover',
    coverageItems: ['Climate and civic trigger bundle', 'Health impact support', 'Business continuity payout'],
    premium: '₹290/week',
    maxCoverageAmount: 'Rs 6,00,000',
  },
]

function Plans() {
  const navigate = useNavigate()
  const [buyingPolicy, setBuyingPolicy] = useState('')
  const [error, setError] = useState('')

  const handleBuyNow = async (policyType) => {
    const targetPolicyType = String(policyType || '').trim()
    if (!targetPolicyType) {
      return
    }

    setBuyingPolicy(targetPolicyType)
    setError('')

    try {
      const location = await resolveCurrentLocation()
      const payload = {
        policy_type: targetPolicyType,
        timestamp: new Date().toISOString(),
      }

      if (location) {
        payload.lat = location.lat
        payload.lng = location.lng
      }

      await buyPolicy(payload)
      navigate('/policy')
    } catch (requestError) {
      const detail = requestError?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Unable to buy this policy right now.')
    } finally {
      setBuyingPolicy('')
    }
  }

  return (
    <section className="plans-page" aria-label="Featured policy plans">
      <header className="plans-header">
        <h1>Our Featured Policies</h1>
      </header>

      {error ? <p className="plans-error">{error}</p> : null}

      <div className="plans-grid">
        {featuredPolicies.map((plan) => (
          <PolicyCard
            key={plan.name}
            mode="plan"
            name={plan.name}
            coverageItems={plan.coverageItems}
            premium={plan.premium}
            maxCoverageAmount={plan.maxCoverageAmount}
            ctaLabel={buyingPolicy === plan.name ? 'Purchasing...' : 'Buy Now'}
            ctaDisabled={Boolean(buyingPolicy)}
            onCtaClick={() => handleBuyNow(plan.name)}
          />
        ))}
      </div>
    </section>
  )
}

export default Plans
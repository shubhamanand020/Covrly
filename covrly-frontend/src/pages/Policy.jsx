import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PolicyCard from '../components/PolicyCard'
import { getMyPolicies, getPolicies, getProfile } from '../services/api'
import './Policy.css'

const getRiskLabel = (riskScore) => {
  const score = Number(riskScore)

  if (!Number.isFinite(score) || score < 0.3) {
    return 'Low'
  }

  if (score <= 0.6) {
    return 'Medium'
  }

  return 'High'
}

const deriveRiskScore = (basePremium, dynamicPremium) => {
  const base = Number(basePremium)
  const dynamic = Number(dynamicPremium)

  if (!Number.isFinite(base) || base <= 0 || !Number.isFinite(dynamic)) {
    return 0
  }

  const computed = (dynamic - base) / base
  if (!Number.isFinite(computed)) {
    return 0
  }

  return Math.max(0, Number(computed.toFixed(4)))
}

function Policy() {
  const navigate = useNavigate()

  const [policies, setPolicies] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [profileComplete, setProfileComplete] = useState(false)

  const loadDynamicPolicies = useCallback(async () => {
    setIsLoading(true)
    setError('')

    try {
      const [profileResponse, catalogResponse, userPoliciesResponse] = await Promise.all([
        getProfile(),
        getPolicies(),
        getMyPolicies(),
      ])

      const isComplete = Boolean(profileResponse?.data?.data?.is_complete)
      const catalog = Array.isArray(catalogResponse?.data) ? catalogResponse.data : []
      const catalogByName = new Map(catalog.map((policy) => [String(policy?.name || ''), policy]))
      const userPolicies = Array.isArray(userPoliciesResponse?.data?.data)
        ? userPoliciesResponse.data.data
        : []

      setProfileComplete(isComplete)

      const enrichedPolicies = userPolicies.map((policy) => {
        const policyName = String(policy?.policy_type || 'Unknown Policy')
        const catalogPolicy = catalogByName.get(policyName) || {}

        const basePremium = Number(policy?.base_premium || 0)
        const dynamicPremium = Number(policy?.dynamic_premium || 0)
        const riskScore = deriveRiskScore(basePremium, dynamicPremium)

        return {
          id: String(policy?.id || policyName),
          name: policyName,
          coverage: catalogPolicy?.coverage || 'Coverage details unavailable',
          zone: catalogPolicy?.zone || 'N/A',
          triggers: Array.isArray(catalogPolicy?.triggers) ? catalogPolicy.triggers : [],
          basePremium,
          dynamicPremium,
          riskScore,
          riskLabel: getRiskLabel(riskScore),
          startDate: policy?.start_date,
          endDate: policy?.end_date,
          status: policy?.status || (policy?.is_active ? 'active' : 'expired'),
          isActive: Boolean(policy?.is_active),
        }
      })

      setPolicies(enrichedPolicies)

      if (!isComplete) {
        setError('Complete your profile before claiming.')
      }
    } catch (requestError) {
      console.error('Failed to load policies', requestError)
      setPolicies([])
      setError('Unable to load policies right now. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDynamicPolicies()
  }, [loadDynamicPolicies])

  const handleClaimClick = (policy) => {
    if (!profileComplete) {
      navigate('/profile')
      return
    }

    if (!policy?.isActive) {
      setError('Policy expired')
      return
    }

    navigate('/claim/manual', {
      state: {
        policyType: policy.name,
      },
    })
  }

  return (
    <section className="policy-page">
      <header className="policy-page-header">
        <h1>Policies</h1>
        <p>Purchased policies with premium, validity window, and claim status</p>
      </header>

      {isLoading ? (
        <p className="policy-page-status">Loading your policies...</p>
      ) : null}

      {error ? <p className="policy-page-error">{error}</p> : null}

      {!isLoading && !error && policies.length === 0 ? (
        <p className="policy-page-status">No purchased policies found.</p>
      ) : null}

      {!isLoading && !error && policies.length > 0 ? (
        <section className="policy-page-grid" aria-label="Policy list">
          {policies.map((policy) => (
            <PolicyCard
              key={policy.id}
              name={policy.name}
              coverage={policy.coverage}
              zone={policy.zone}
              triggers={policy.triggers}
              basePremium={policy.basePremium}
              dynamicPremium={policy.dynamicPremium}
              riskLabel={policy.riskLabel}
              riskScore={policy.riskScore}
              startDate={policy.startDate}
              endDate={policy.endDate}
              status={policy.status}
              claimDisabled={!policy.isActive || !profileComplete}
              onClaimClick={() => handleClaimClick(policy)}
            />
          ))}
        </section>
      ) : null}
    </section>
  )
}

export default Policy

import { useEffect, useState } from 'react'
import { FileText, Search, ShieldCheck, UserRound, Zap } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getMyPolicies, getProfile } from '../services/api'
import './Dashboard.css'

const COVERAGE_HINTS = {
  'Holistic Cover': 'Comprehensive multi-risk protection',
  HeatGuard: 'Heat and climate disruption protection',
  'RainSure Cover': 'Rain and flood disruption protection',
  'CivicShield Cover': 'Traffic and civic disruption protection',
}

const actionItems = [
  { label: 'Active Coverage', route: '/policy', Icon: ShieldCheck },
  { label: 'Claim Now', route: '/claim/manual', Icon: FileText },
  { label: 'Trigger Status', route: '/auto-flow', Icon: Zap },
  { label: 'Explore Plans', route: '/plans', Icon: Search },
  { label: 'Profile & Settings', route: '/settings', Icon: UserRound, centered: true },
]

function Dashboard() {
  const navigate = useNavigate()
  const [loadingProfile, setLoadingProfile] = useState(true)
  const [loadingPolicies, setLoadingPolicies] = useState(true)
  const [profileError, setProfileError] = useState('')
  const [policiesError, setPoliciesError] = useState('')
  const [purchasedPolicies, setPurchasedPolicies] = useState([])
  const [activePolicyIndex, setActivePolicyIndex] = useState(0)

  const hasPolicies = purchasedPolicies.length > 0
  const hasMultiplePolicies = purchasedPolicies.length > 1
  const activePolicy = hasPolicies ? purchasedPolicies[activePolicyIndex] : null

  const formatDate = (value) => {
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
      return 'N/A'
    }

    return parsed.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  }

  const formatWeeklyPremium = (value) => {
    const amount = Number(value)
    if (!Number.isFinite(amount)) {
      return 'N/A'
    }
    return `Rs ${amount.toLocaleString('en-IN')}/week`
  }

  const resolveCoverage = (policyType) => {
    const key = String(policyType || '').trim()
    return COVERAGE_HINTS[key] || 'Coverage as per selected plan terms'
  }

  const goToPreviousPolicy = () => {
    setActivePolicyIndex((previous) => {
      if (!purchasedPolicies.length) {
        return 0
      }
      return (previous - 1 + purchasedPolicies.length) % purchasedPolicies.length
    })
  }

  const goToNextPolicy = () => {
    setActivePolicyIndex((previous) => {
      if (!purchasedPolicies.length) {
        return 0
      }
      return (previous + 1) % purchasedPolicies.length
    })
  }

  const triggerCardRipple = (event) => {
    const element = event.currentTarget
    const bounds = element.getBoundingClientRect()
    const x = event.clientX - bounds.left
    const y = event.clientY - bounds.top

    element.style.setProperty('--ripple-x', `${x}px`)
    element.style.setProperty('--ripple-y', `${y}px`)
    element.classList.remove('is-rippling')
    void element.offsetWidth
    element.classList.add('is-rippling')
  }

  useEffect(() => {
    let isMounted = true

    const enforceProfileCompletion = async () => {
      setLoadingProfile(true)
      setLoadingPolicies(true)
      setProfileError('')
      setPoliciesError('')

      let isComplete = false

      try {
        const response = await getProfile()
        isComplete = Boolean(response?.data?.data?.is_complete)

        if (!isMounted) {
          return
        }

        if (!isComplete) {
          setLoadingPolicies(false)
          navigate('/profile', { replace: true })
          return
        }
      } catch (requestError) {
        const detail = requestError?.response?.data?.detail
        if (isMounted) {
          const normalizedDetail =
            typeof detail === 'string'
              ? detail
              : 'Unable to verify profile right now. Please try again.'
          setProfileError(normalizedDetail)
          setLoadingPolicies(false)
        }
        return
      } finally {
        if (isMounted) {
          setLoadingProfile(false)
        }
      }

      if (!isComplete || !isMounted) {
        return
      }

      try {
        const policyResponse = await getMyPolicies()
        if (!isMounted) {
          return
        }

        const rawPolicies = Array.isArray(policyResponse?.data?.data)
          ? policyResponse.data.data
          : []

        const sortedPolicies = [...rawPolicies].sort((left, right) => {
          const leftActive = Boolean(left?.is_active)
          const rightActive = Boolean(right?.is_active)

          if (leftActive !== rightActive) {
            return leftActive ? -1 : 1
          }

          const leftTime = new Date(left?.created_at || 0).getTime()
          const rightTime = new Date(right?.created_at || 0).getTime()
          return rightTime - leftTime
        })

        setPurchasedPolicies(sortedPolicies)
      } catch (requestError) {
        const detail = requestError?.response?.data?.detail
        if (isMounted) {
          setPoliciesError(
            typeof detail === 'string'
              ? detail
              : 'Unable to load policies right now. Please try again.',
          )
        }
      } finally {
        if (isMounted) {
          setLoadingPolicies(false)
        }
      }
    }

    enforceProfileCompletion()

    return () => {
      isMounted = false
    }
  }, [navigate])

  useEffect(() => {
    if (!purchasedPolicies.length) {
      setActivePolicyIndex(0)
      return
    }

    setActivePolicyIndex((previous) => {
      if (previous < purchasedPolicies.length) {
        return previous
      }
      return 0
    })
  }, [purchasedPolicies])

  if (loadingProfile || loadingPolicies) {
    return (
      <section className="dashboard">
        <p className="dashboard-info">Loading dashboard...</p>
      </section>
    )
  }

  if (profileError) {
    return (
      <section className="dashboard">
        <p className="dashboard-error">{profileError}</p>
      </section>
    )
  }

  return (
    <section className="dashboard">
      <header className="dashboard-header">
        <h1>Covrly</h1>
      </header>

      <section className="dashboard-policy-section" aria-label="Purchased policies">
        <div className="dashboard-policy-controls-row">
          <p className="dashboard-policy-heading">Your Policies</p>

          {hasMultiplePolicies ? (
            <div className="dashboard-policy-controls" role="group" aria-label="Policy slider controls">
              <button
                type="button"
                className="dashboard-policy-nav"
                onClick={goToPreviousPolicy}
                aria-label="Previous policy"
              >
                {'<'}
              </button>
              <span className="dashboard-policy-counter">
                {activePolicyIndex + 1} / {purchasedPolicies.length}
              </span>
              <button
                type="button"
                className="dashboard-policy-nav"
                onClick={goToNextPolicy}
                aria-label="Next policy"
              >
                {'>'}
              </button>
            </div>
          ) : null}
        </div>

        {policiesError ? <p className="dashboard-policy-error">{policiesError}</p> : null}

        <article className="policy-card" aria-label="Active policy">
          {activePolicy ? (
            <>
              <div className="policy-card-top">
                <h2 className="policy-name">{activePolicy.policy_type || 'Policy'}</h2>
                <span className={`policy-status ${activePolicy.is_active ? 'policy-status-active' : 'policy-status-expired'}`}>
                  {activePolicy.is_active ? 'Active' : 'Expired'}
                </span>
              </div>

              <div className="policy-meta-grid">
                <div className="policy-meta-item">
                  <span className="policy-meta-label">Coverage</span>
                  <span className="policy-meta-value">{resolveCoverage(activePolicy.policy_type)}</span>
                </div>
                <div className="policy-meta-item">
                  <span className="policy-meta-label">Premium</span>
                  <span className="policy-meta-value">
                    {formatWeeklyPremium(activePolicy.dynamic_premium ?? activePolicy.base_premium)}
                  </span>
                </div>
                <div className="policy-meta-item">
                  <span className="policy-meta-label">Valid till</span>
                  <span className="policy-meta-value">{formatDate(activePolicy.end_date)}</span>
                </div>
                <div className="policy-meta-item">
                  <span className="policy-meta-label">Policy ID</span>
                  <span className="policy-meta-value policy-meta-id">{activePolicy.id || 'N/A'}</span>
                </div>
              </div>
            </>
          ) : (
            <div className="dashboard-empty-policy-state">
              <h2 className="policy-name">No purchased policies yet</h2>
              <p>Explore plans to activate your first coverage.</p>
              <button type="button" className="dashboard-empty-policy-cta" onClick={() => navigate('/plans')}>
                Explore plans
              </button>
            </div>
          )}
        </article>

        {hasMultiplePolicies ? (
          <div className="dashboard-policy-dots">
            {purchasedPolicies.map((policy, index) => (
              <button
                key={policy.id || `${policy.policy_type}-${index}`}
                type="button"
                className={`dashboard-policy-dot ${index === activePolicyIndex ? 'is-active' : ''}`}
                onClick={() => setActivePolicyIndex(index)}
                aria-label={`Go to policy ${index + 1}`}
              />
            ))}
          </div>
        ) : null}
      </section>

      <section className="dashboard-actions" aria-label="Workflow actions">
        <div className="dashboard-grid">
          {actionItems.map((item) => (
            <button
              key={item.label}
              type="button"
              className={[
                'dashboard-card',
                item.featured ? 'dashboard-card-featured' : '',
                item.centered ? 'dashboard-card-centered' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onPointerDown={triggerCardRipple}
              onClick={() => navigate(item.route)}
            >
              <span className="dashboard-card-icon-wrap" aria-hidden="true">
                <item.Icon className="dashboard-card-icon" size={32} strokeWidth={2.1} />
              </span>
              <span className="dashboard-card-label">{item.label}</span>
            </button>
          ))}
        </div>
      </section>
    </section>
  )
}

export default Dashboard

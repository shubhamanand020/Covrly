import './PolicyCard.css'

function PolicyCard({
  name,
  coverage,
  zone,
  validTill,
  startDate,
  endDate,
  status,
  triggers = [],
  basePremium,
  dynamicPremium,
  riskLabel,
  riskScore,
  mode = 'policy',
  coverageItems = [],
  premium,
  maxCoverageAmount,
  ctaLabel = 'Buy Now',
  ctaDisabled = false,
  claimDisabled = false,
  onClaimClick,
  onCtaClick,
}) {
  const isPlanMode = mode === 'plan'
  const hasDynamicPremium = Number.isFinite(Number(basePremium)) && Number.isFinite(Number(dynamicPremium))
  const normalizedRiskLabel = String(riskLabel || 'Unknown').toLowerCase()
  const normalizedStatus = String(status || '').toLowerCase()
  const isExpired = normalizedStatus === 'expired'

  const formatRupees = (value) => {
    const amount = Number(value)
    if (!Number.isFinite(amount)) {
      return '₹0/week'
    }
    return `₹${amount.toLocaleString('en-IN')}/week`
  }

  const formatDate = (value) => {
    const normalized = String(value || '').trim()
    if (!normalized) {
      return 'N/A'
    }

    const parsed = new Date(normalized)
    if (Number.isNaN(parsed.getTime())) {
      return normalized
    }

    return parsed.toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  return (
    <article
      className={`policycard${isPlanMode ? ' policycard-plan' : ''}`}
      aria-label={`${name} policy`}
    >
      <header className="policycard-header">
        <h2 className="policycard-title">{name}</h2>
      </header>

      {isPlanMode ? (
        <>
          <section className="policycard-plan-coverage" aria-label="Coverage items">
            <p className="policycard-plan-section-label">Coverage items</p>
            <ul className="policycard-plan-list">
              {coverageItems.length > 0 ? (
                coverageItems.map((item) => <li key={`${name}-${item}`}>{item}</li>)
              ) : (
                <li>Coverage details will be available soon</li>
              )}
            </ul>
          </section>

          <dl className="policycard-plan-meta">
            <div className="policycard-detail-item">
              <dt>Premium</dt>
              <dd>{premium}</dd>
            </div>
            <div className="policycard-detail-item">
              <dt>Maximum coverage amount</dt>
              <dd>{maxCoverageAmount}</dd>
            </div>
          </dl>

          <button
            type="button"
            className="policycard-buy-button"
            onClick={onCtaClick}
            disabled={ctaDisabled}
          >
            {ctaLabel}
          </button>
        </>
      ) : (
        <>
          <dl className="policycard-details">
            <div className="policycard-detail-item">
              <dt>Coverage</dt>
              <dd>{coverage}</dd>
            </div>
            {zone ? (
              <div className="policycard-detail-item">
                <dt>Zone</dt>
                <dd>{zone}</dd>
              </div>
            ) : null}
            <div className="policycard-detail-item">
              <dt>Start</dt>
              <dd>{formatDate(startDate)}</dd>
            </div>
            <div className="policycard-detail-item">
              <dt>End</dt>
              <dd>{formatDate(endDate || validTill)}</dd>
            </div>
            <div className="policycard-detail-item">
              <dt>Status</dt>
              <dd>
                <span className={`policycard-status policycard-status-${isExpired ? 'expired' : 'active'}`}>
                  {isExpired ? 'Expired' : 'Active'}
                </span>
              </dd>
            </div>
          </dl>

          {hasDynamicPremium ? (
            <section className="policycard-pricing" aria-label="Dynamic premium">
              <p className="policycard-pricing-label">Premium</p>
              <p className="policycard-pricing-row">
                <span>Base</span>
                <strong>{formatRupees(basePremium)}</strong>
              </p>
              <p className="policycard-pricing-row">
                <span>Dynamic</span>
                <strong>{formatRupees(dynamicPremium)}</strong>
              </p>
              <p className="policycard-pricing-row">
                <span>Risk</span>
                <span className={`policycard-risk-badge policycard-risk-${normalizedRiskLabel}`}>
                  {riskLabel}
                  {Number.isFinite(Number(riskScore)) ? ` (${Number(riskScore).toFixed(2)})` : ''}
                </span>
              </p>
            </section>
          ) : null}

          <section className="policycard-triggers" aria-label="Policy triggers">
            <p className="policycard-triggers-label">Triggers</p>
            <div className="policycard-trigger-list">
              {triggers.length > 0 ? (
                triggers.map((trigger) => (
                  <span key={trigger} className="policycard-trigger-tag">
                    {trigger}
                  </span>
                ))
              ) : (
                <span className="policycard-trigger-empty">No triggers configured</span>
              )}
            </div>
          </section>

          <button
            type="button"
            className="policycard-claim-button"
            onClick={onClaimClick}
            disabled={claimDisabled}
          >
            {claimDisabled ? 'Claim unavailable' : 'Claim with this policy'}
          </button>
        </>
      )}
    </article>
  )
}

export default PolicyCard
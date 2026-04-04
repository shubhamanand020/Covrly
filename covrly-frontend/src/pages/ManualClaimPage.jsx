import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { getMyPolicies, getProfile, submitManualClaim } from '../services/api'
import LocationPicker from '../components/LocationPicker'
import './Claim.css'

const formatTodayDate = () => new Date().toISOString().slice(0, 10)

const buildClaimTimestamp = (dateValue, timeValue) => {
  const safeDate = String(dateValue || '').trim()
  const safeTime = String(timeValue || '').trim()

  if (!safeDate || !safeTime) {
    return new Date().toISOString()
  }

  const localDate = new Date(`${safeDate}T${safeTime}:00`)
  if (Number.isNaN(localDate.getTime())) {
    return new Date().toISOString()
  }

  const offsetMinutes = -localDate.getTimezoneOffset()
  const sign = offsetMinutes >= 0 ? '+' : '-'
  const absoluteOffset = Math.abs(offsetMinutes)
  const offsetHours = String(Math.floor(absoluteOffset / 60)).padStart(2, '0')
  const offsetRemainderMinutes = String(absoluteOffset % 60).padStart(2, '0')

  return `${safeDate}T${safeTime}:00${sign}${offsetHours}:${offsetRemainderMinutes}`
}

const readFileAsBase64 = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result)
        return
      }
      resolve('')
    }
    reader.onerror = () => reject(new Error('Unable to read selected image'))
    reader.readAsDataURL(file)
  })

function ManualClaimPage() {
  const navigate = useNavigate()
  const location = useLocation()

  const requestedPolicyType = String(location.state?.policyType || '').trim()

  const [formData, setFormData] = useState({
    policy: '',
    date: formatTodayDate(),
    time: '21:00',
  })
  const [activePolicies, setActivePolicies] = useState([])
  const [selectedLocation, setSelectedLocation] = useState(null)
  const [selectedImage, setSelectedImage] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [precheckLoading, setPrecheckLoading] = useState(true)

  const policyOptions = useMemo(
    () => activePolicies.map((policy) => String(policy.policy_type || '').trim()).filter(Boolean),
    [activePolicies],
  )

  useEffect(() => {
    let isMounted = true

    const runPrechecks = async () => {
      setPrecheckLoading(true)
      setError('')

      try {
        const [profileResponse, policiesResponse] = await Promise.all([getProfile(), getMyPolicies()])

        const profileData = profileResponse?.data?.data || {}
        if (!profileData.is_complete) {
          navigate('/profile', { replace: true })
          return
        }

        const allPolicies = Array.isArray(policiesResponse?.data?.data) ? policiesResponse.data.data : []
        const active = allPolicies.filter((policy) => Boolean(policy?.is_active))

        if (!isMounted) {
          return
        }

        setActivePolicies(active)

        const requestedPolicy = active.find(
          (policy) => String(policy?.policy_type || '').trim() === requestedPolicyType,
        )

        setFormData((prev) => ({
          ...prev,
          policy: requestedPolicy?.policy_type || active[0]?.policy_type || '',
        }))

        if (active.length === 0) {
          setError('No active policy found. Buy a policy before submitting claims.')
        }
      } catch (requestError) {
        const detail = requestError?.response?.data?.detail
        if (isMounted) {
          setError(typeof detail === 'string' ? detail : 'Unable to load your policy details.')
        }
      } finally {
        if (isMounted) {
          setPrecheckLoading(false)
        }
      }
    }

    runPrechecks()

    return () => {
      isMounted = false
    }
  }, [navigate, requestedPolicyType])

  const handleInputChange = (event) => {
    const { name, value } = event.target
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const handleFileChange = (event) => {
    const file = event.target.files && event.target.files[0] ? event.target.files[0] : null
    setSelectedImage(file)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)

    if (!formData.policy) {
      setError('Select an active policy before submitting your claim.')
      setLoading(false)
      return
    }

    if (!selectedLocation) {
      setError('Please choose a location from the map.')
      setLoading(false)
      return
    }

    const timestamp = buildClaimTimestamp(formData.date, formData.time)
    const selectedPolicy = formData.policy || 'Holistic Cover'

    try {
      const encodedImage = selectedImage ? await readFileAsBase64(selectedImage) : null
      const payload = {
        policy_type: selectedPolicy,
        lat: selectedLocation.lat,
        lng: selectedLocation.lng,
        timestamp,
        image: encodedImage,
        image_metadata: {
          image_name: selectedImage ? selectedImage.name : null,
          user_location: selectedLocation,
          timestamp,
          date: formData.date,
          time: formData.time,
          policy_type: selectedPolicy,
        },
      }

      const response = await submitManualClaim(payload)
      const flowResponse = response?.data || {}
      const status = String(flowResponse.status || '').toLowerCase()
      const nextStep = String(flowResponse.next_step || '').toLowerCase()

      if (status === 'approved' && nextStep === 'payout') {
        navigate('/payout', { state: flowResponse })
        return
      }

      if (status === 'rejected') {
        navigate('/payout', { state: flowResponse })
        return
      }

      if (status === 'verification_required' && nextStep === 'verify') {
        navigate('/verification', { state: flowResponse })
        return
      }

      setError('Unexpected response from server. Please try again.')
    } catch (submitError) {
      const detail = submitError?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Server error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="claim-page">
      <header className="claim-header">
        <h1>Claim Submission</h1>
        <p>Submit policy, location, timestamp, and geotagged image.</p>
      </header>

      {precheckLoading ? (
        <p className="claim-feedback claim-feedback-info">Checking profile and policy status...</p>
      ) : null}

      <form className="claim-form" onSubmit={handleSubmit}>
        <label className="claim-field" htmlFor="policy">
          Policy
          <select
            id="policy"
            name="policy"
            value={formData.policy}
            onChange={handleInputChange}
            required
            disabled={precheckLoading || policyOptions.length === 0}
          >
            {policyOptions.length > 0 ? (
              policyOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))
            ) : (
              <option value="">No active policies</option>
            )}
          </select>
        </label>

        <LocationPicker value={selectedLocation} onChange={setSelectedLocation} />

        <div className="claim-time-grid">
          <label className="claim-field" htmlFor="date">
            Date
            <input
              id="date"
              name="date"
              type="date"
              value={formData.date}
              onChange={handleInputChange}
              required
            />
          </label>

          <label className="claim-field" htmlFor="time">
            Time
            <input
              id="time"
              name="time"
              type="time"
              value={formData.time}
              onChange={handleInputChange}
              required
            />
          </label>
        </div>

        <label className="claim-field" htmlFor="imageUpload">
          Geotagged image
          <input
            id="imageUpload"
            name="imageUpload"
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            required
          />
          {selectedImage ? (
            <span className="claim-file-name">Selected: {selectedImage.name}</span>
          ) : null}
        </label>

        {error ? <p className="claim-feedback claim-feedback-error">{error}</p> : null}

        <button
          type="submit"
          className="claim-submit-button"
          disabled={loading || precheckLoading || policyOptions.length === 0}
        >
          {loading ? 'Submitting...' : 'Submit Manual Claim'}
        </button>
      </form>
    </section>
  )
}

export default ManualClaimPage

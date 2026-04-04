import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { verifyAutoFlow } from '../services/api'
import './Verification.css'

const readFileAsBase64 = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('Failed to read image'))
    reader.readAsDataURL(file)
  })

function Verification() {
  const navigate = useNavigate()
  const location = useLocation()
  const [selectedImage, setSelectedImage] = useState(null)
  const [userLocation, setUserLocation] = useState(null)
  const [isLocationLoading, setIsLocationLoading] = useState(true)
  const [locationError, setLocationError] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const flowResponse = useMemo(() => {
    if (location?.state && typeof location.state === 'object' && !Array.isArray(location.state)) {
      return location.state
    }
    return null
  }, [location?.state])

  const flowStatus = String(flowResponse?.status || '').toLowerCase()
  const flowData = flowResponse?.data && typeof flowResponse.data === 'object' ? flowResponse.data : {}

  const requestUserLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setUserLocation(null)
      setLocationError('Unable to fetch location. Please enable location access.')
      setIsLocationLoading(false)
      return
    }

    setIsLocationLoading(true)
    setLocationError('')

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setUserLocation({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        })
        setIsLocationLoading(false)
      },
      (geoError) => {
        console.error('Geolocation error:', geoError)
        setUserLocation(null)
        setLocationError('Unable to fetch location. Please enable location access.')
        setIsLocationLoading(false)
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
      },
    )
  }, [])

  useEffect(() => {
    requestUserLocation()
  }, [requestUserLocation])

  const handleFileChange = (event) => {
    const file = event.target.files && event.target.files[0] ? event.target.files[0] : null
    setSelectedImage(file)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setMessage('')
    setError('')

    if (!userLocation) {
      setError('Unable to fetch location. Please enable location access.')
      return
    }

    if (!selectedImage) {
      setError('Please upload an image before submitting verification.')
      return
    }

    setIsSubmitting(true)

    try {
      const timestamp = new Date().toISOString()
      const encodedImage = selectedImage ? await readFileAsBase64(selectedImage) : null
      const payload = {
        claim_id: flowData?.claim_id,
        user_id: flowData?.user_id || 'demo-user',
        user_location: userLocation,
        timestamp,
        image: encodedImage,
        image_metadata: {
          image_name: selectedImage?.name || null,
          user_location: userLocation,
          timestamp,
        },
      }

      const response = await verifyAutoFlow(payload)
      const verifyResponse = response?.data || {}
      const status = String(verifyResponse.status || '').toLowerCase()
      const nextStep = String(verifyResponse.next_step || '').toLowerCase()

      if (status === 'approved' && nextStep === 'payout') {
        navigate('/payout', { state: verifyResponse })
        return
      }

      if (status === 'rejected') {
        const reason = verifyResponse?.data?.reason
        setError(typeof reason === 'string' ? reason : 'Verification failed. Claim rejected.')
        return
      }

      setMessage('Verification is still in progress.')
    } catch (requestError) {
      const detail = requestError?.response?.data?.detail
      if (typeof detail === 'string') {
        setError(detail)
      } else if (requestError instanceof Error && requestError.message) {
        setError(requestError.message)
      } else {
        setError('Server error during verification. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (flowStatus !== 'verification_required') {
    return (
      <section className="verification-page">
        <article className="verification-card">
          <h1>Verification</h1>
          <p className="verification-text">No pending verification claim found.</p>
          <button
            type="button"
            className="verification-button"
            onClick={() => navigate('/dashboard')}
          >
            Go Back to Dashboard
          </button>
        </article>
      </section>
    )
  }

  return (
    <section className="verification-page">
      <article className="verification-card">
        <h1>Verification Required</h1>
        <p className="verification-text">
          Upload a geotagged selfie/image to complete auto-flow verification.
        </p>

        {isLocationLoading ? (
          <p className="verification-feedback verification-feedback-info">Fetching your location...</p>
        ) : null}

        {!isLocationLoading && userLocation ? (
          <p className="verification-file">
            Location: {userLocation.lat.toFixed(6)}, {userLocation.lng.toFixed(6)}
          </p>
        ) : null}

        {locationError ? (
          <p className="verification-feedback verification-feedback-error">{locationError}</p>
        ) : null}

        {locationError ? (
          <button
            type="button"
            className="verification-button"
            onClick={requestUserLocation}
            disabled={isLocationLoading || isSubmitting}
          >
            {isLocationLoading ? 'Fetching Location...' : 'Retry Location'}
          </button>
        ) : null}

        <form className="verification-form" onSubmit={handleSubmit}>
          <label className="verification-field" htmlFor="verificationImage">
            Upload verification image
            <input
              id="verificationImage"
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              required
            />
          </label>

          {selectedImage ? (
            <p className="verification-file">Selected: {selectedImage.name}</p>
          ) : null}

          {message ? <p className="verification-feedback verification-feedback-info">{message}</p> : null}
          {error ? <p className="verification-feedback verification-feedback-error">{error}</p> : null}

          <button
            type="submit"
            className="verification-button"
            disabled={isSubmitting || isLocationLoading || !selectedImage || !userLocation}
          >
            {isSubmitting ? 'Submitting...' : 'Submit Verification'}
          </button>
        </form>
      </article>
    </section>
  )
}

export default Verification

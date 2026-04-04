import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getProfile, upsertProfile } from '../services/api'
import './Profile.css'

const initialProfile = {
  name: '',
  phone: '',
  city: '',
  vehicle_type: '',
  profile_image_url: '',
}

const readFileAsDataUrl = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('Unable to read image file'))
    reader.readAsDataURL(file)
  })

function Profile() {
  const [profile, setProfile] = useState(initialProfile)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const navigate = useNavigate()

  useEffect(() => {
    let isMounted = true

    const loadProfile = async () => {
      setLoading(true)
      setError('')

      try {
        const response = await getProfile()
        const data = response?.data?.data || {}
        if (!isMounted) {
          return
        }

        setProfile({
          name: String(data.name || ''),
          phone: String(data.phone || ''),
          city: String(data.city || ''),
          vehicle_type: String(data.vehicle_type || ''),
          profile_image_url: String(data.profile_image_url || ''),
        })
      } catch (requestError) {
        const detail = requestError?.response?.data?.detail
        if (isMounted) {
          setError(typeof detail === 'string' ? detail : 'Unable to load profile right now.')
        }
      } finally {
        if (isMounted) {
          setLoading(false)
        }
      }
    }

    loadProfile()

    return () => {
      isMounted = false
    }
  }, [])

  const handleChange = (event) => {
    const { name, value } = event.target
    setProfile((previous) => ({
      ...previous,
      [name]: value,
    }))

    if (error) {
      setError('')
    }
    if (message) {
      setMessage('')
    }
  }

  const handleImageChange = async (event) => {
    const selectedFile = event.target.files && event.target.files[0] ? event.target.files[0] : null
    if (!selectedFile) {
      return
    }

    if (!String(selectedFile.type || '').toLowerCase().startsWith('image/')) {
      setError('Please upload a valid image file.')
      event.target.value = ''
      return
    }

    if (Number(selectedFile.size || 0) > 2 * 1024 * 1024) {
      setError('Profile image must be 2MB or less.')
      event.target.value = ''
      return
    }

    try {
      const imageDataUrl = await readFileAsDataUrl(selectedFile)
      setProfile((previous) => ({
        ...previous,
        profile_image_url: imageDataUrl,
      }))
      setError('')
      setMessage('')
    } catch {
      setError('Unable to process profile image. Please try another image.')
    } finally {
      event.target.value = ''
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()

    setSaving(true)
    setError('')
    setMessage('')

    try {
      const payload = {
        name: String(profile.name || '').trim(),
        phone: String(profile.phone || '').trim(),
        city: String(profile.city || '').trim(),
        vehicle_type: String(profile.vehicle_type || '').trim(),
        profile_image_url: String(profile.profile_image_url || '').trim(),
      }

      if (!payload.profile_image_url) {
        setError('Add your profile image to complete profile setup.')
        return
      }

      const response = await upsertProfile(payload)
      const isComplete = Boolean(response?.data?.data?.is_complete)

      if (isComplete) {
        setMessage('Profile saved. You can now submit claims.')
        navigate('/dashboard')
      } else {
        setMessage('Profile saved as draft. Complete all fields before claiming.')
      }
    } catch (requestError) {
      const detail = requestError?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Unable to save profile right now.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="profile-page">
      <header className="profile-header">
        <h1>Profile</h1>
        <p>Complete these details before creating claims.</p>
      </header>

      {loading ? <p className="profile-feedback">Loading profile...</p> : null}
      {error ? <p className="profile-feedback profile-feedback-error">{error}</p> : null}
      {message ? <p className="profile-feedback profile-feedback-success">{message}</p> : null}

      <form className="profile-form" onSubmit={handleSubmit} aria-busy={saving}>
        <div className="profile-photo-section">
          <div className="profile-photo-preview-wrap">
            {profile.profile_image_url ? (
              <img src={profile.profile_image_url} alt="Profile preview" className="profile-photo-preview" />
            ) : (
              <span className="profile-photo-placeholder" aria-hidden="true">
                Add photo
              </span>
            )}
          </div>
          <label htmlFor="profile-image" className="profile-photo-upload-btn">
            Upload image
          </label>
          <input
            id="profile-image"
            type="file"
            accept="image/*"
            className="profile-photo-input"
            onChange={handleImageChange}
          />
        </div>

        <label className="profile-field" htmlFor="profile-name">
          Name
          <input
            id="profile-name"
            name="name"
            type="text"
            value={profile.name}
            onChange={handleChange}
            autoComplete="name"
            required
          />
        </label>

        <label className="profile-field" htmlFor="profile-phone">
          Phone
          <input
            id="profile-phone"
            name="phone"
            type="tel"
            value={profile.phone}
            onChange={handleChange}
            autoComplete="tel"
            required
          />
        </label>

        <label className="profile-field" htmlFor="profile-city">
          City
          <input
            id="profile-city"
            name="city"
            type="text"
            value={profile.city}
            onChange={handleChange}
            autoComplete="address-level2"
            required
          />
        </label>

        <label className="profile-field" htmlFor="profile-vehicle-type">
          Vehicle Type
          <input
            id="profile-vehicle-type"
            name="vehicle_type"
            type="text"
            value={profile.vehicle_type}
            onChange={handleChange}
            placeholder="Car, Bike, Scooter, etc."
            required
          />
        </label>

        <button className="profile-edit-button" type="submit" disabled={saving || loading}>
          {saving ? 'Saving...' : 'Save Profile'}
        </button>
      </form>
    </section>
  )
}

export default Profile
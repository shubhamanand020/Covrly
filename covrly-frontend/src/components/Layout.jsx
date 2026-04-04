import { useCallback, useEffect, useRef, useState } from 'react'
import { FileText, LayoutDashboard, Search, User, Zap } from 'lucide-react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import Navbar from './Navbar'
import BottomNav from './BottomNav'
import TriggerPopup from './TriggerPopup'
import { clearToken, getProfile, monitorLocation, upsertProfile } from '../services/api'
import './Layout.css'

const backDisabledRoutes = new Set(['/login', '/dashboard'])
const DEFAULT_MONITOR_INTERVAL_MS = 45000

const emptyProfile = {
  name: '',
  phone: '',
  city: '',
  vehicle_type: '',
  profile_image_url: '',
  is_complete: false,
}

const TRIGGER_PRESENTATION = {
  rain: {
    disruption: 'Heavy Rain',
    policy: 'RainSure Cover',
    eligiblePayout: 'INR 8,000',
  },
  traffic_congestion: {
    disruption: 'Traffic Congestion',
    policy: 'CivicShield Cover',
    eligiblePayout: 'INR 10,000',
  },
  traffic: {
    disruption: 'Traffic Disruption',
    policy: 'CivicShield Cover',
    eligiblePayout: 'INR 10,000',
  },
}

const DEFAULT_TRIGGER_PRESENTATION = {
  disruption: 'Travel Disruption',
  policy: 'Holistic Cover',
  eligiblePayout: 'As per policy terms',
}

const profileSidebarItems = [
  { label: 'Profile', path: '/profile', Icon: User },
  { label: 'My policies', path: '/policy', Icon: FileText },
  { label: 'Explore policies', path: '/plans', Icon: Search },
  { label: 'My triggers', path: '/tracking', Icon: Zap },
]

const normalizeTriggerType = (value) => String(value || 'unknown').trim().toLowerCase()

const normalizeProfileData = (payload) => {
  const data = payload && typeof payload === 'object' ? payload : {}
  return {
    name: String(data.name || ''),
    phone: String(data.phone || ''),
    city: String(data.city || ''),
    vehicle_type: String(data.vehicle_type || ''),
    profile_image_url: String(data.profile_image_url || ''),
    is_complete: Boolean(data.is_complete),
  }
}

const toProfileDraft = (profile) => ({
  name: String(profile?.name || ''),
  phone: String(profile?.phone || ''),
  city: String(profile?.city || ''),
  vehicle_type: String(profile?.vehicle_type || ''),
  profile_image_url: String(profile?.profile_image_url || ''),
})

const readFileAsDataUrl = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('Unable to read image file'))
    reader.readAsDataURL(file)
  })

const buildTriggerFingerprint = (trigger) => {
  const triggerId = String(trigger?.trigger_id || '').trim()
  if (triggerId) {
    return triggerId
  }

  const type = normalizeTriggerType(trigger?.trigger_type)
  const timestamp = String(trigger?.timestamp || '')
  const lat = Number(trigger?.location?.lat)
  const lng = Number(trigger?.location?.lng)
  return `${type}|${timestamp}|${lat}|${lng}`
}

const resolveClaimLocation = (trigger, fallbackPosition) => {
  const triggerLat = Number(trigger?.location?.lat)
  const triggerLng = Number(trigger?.location?.lng)

  if (Number.isFinite(triggerLat) && Number.isFinite(triggerLng)) {
    return {
      lat: triggerLat,
      lng: triggerLng,
    }
  }

  return {
    lat: Number(fallbackPosition?.lat ?? 12.9716),
    lng: Number(fallbackPosition?.lng ?? 77.5946),
  }
}

function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const secureContext = typeof window === 'undefined' ? true : window.isSecureContext
  const geolocationSupported = secureContext && typeof navigator !== 'undefined' && 'geolocation' in navigator
  const permissionsSupported =
    typeof navigator !== 'undefined' &&
    navigator.permissions &&
    typeof navigator.permissions.query === 'function'
  const latestPositionRef = useRef(null)
  const lastSentAtRef = useRef(0)
  const seenTriggerFingerprintsRef = useRef(new Set())
  const [permissionState, setPermissionState] = useState(
    geolocationSupported ? (permissionsSupported ? 'checking' : 'prompt') : 'unsupported',
  )
  const [monitorState, setMonitorState] = useState('idle')
  const [monitorHint, setMonitorHint] = useState(
    geolocationSupported
      ? ''
      : secureContext
        ? 'Geolocation is not supported in this browser.'
        : 'Location APIs require HTTPS or localhost. Open this app on localhost or HTTPS.',
  )
  const [latestPosition, setLatestPosition] = useState(null)
  const [lastSyncTimestamp, setLastSyncTimestamp] = useState('')
  const [lastDetectedTrigger, setLastDetectedTrigger] = useState(null)
  const [activeTriggerPopup, setActiveTriggerPopup] = useState(null)
  const [profileState, setProfileState] = useState({
    loading: true,
    data: emptyProfile,
  })
  const [profileDraft, setProfileDraft] = useState(toProfileDraft(emptyProfile))
  const [profileModalOpen, setProfileModalOpen] = useState(false)
  const [profileModalSaving, setProfileModalSaving] = useState(false)
  const [profileModalError, setProfileModalError] = useState('')
  const [profileModalInfo, setProfileModalInfo] = useState('')
  const [profileMenuOpen, setProfileMenuOpen] = useState(false)

  const showBack = !backDisabledRoutes.has(location.pathname)

  const handleBack = () => {
    navigate(-1)
  }

  const loadProfile = useCallback(async () => {
    setProfileState((previous) => ({
      ...previous,
      loading: true,
    }))

    try {
      const response = await getProfile()
      const normalized = normalizeProfileData(response?.data?.data)

      setProfileState({
        loading: false,
        data: normalized,
      })
      setProfileDraft(toProfileDraft(normalized))
      setProfileModalOpen(!normalized.is_complete)
    } catch {
      setProfileState((previous) => ({
        ...previous,
        loading: false,
      }))
    }
  }, [])

  useEffect(() => {
    void loadProfile()
  }, [loadProfile])

  useEffect(() => {
    setProfileMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!profileMenuOpen && !profileModalOpen) {
      return undefined
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [profileMenuOpen, profileModalOpen])

  useEffect(() => {
    if (!profileMenuOpen) {
      return undefined
    }

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        setProfileMenuOpen(false)
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [profileMenuOpen])

  const handleProfileDraftChange = (event) => {
    const { name, value } = event.target
    setProfileDraft((previous) => ({
      ...previous,
      [name]: value,
    }))

    if (profileModalError) {
      setProfileModalError('')
    }

    if (profileModalInfo) {
      setProfileModalInfo('')
    }
  }

  const handleProfileImageChange = async (event) => {
    const selectedFile = event.target.files && event.target.files[0] ? event.target.files[0] : null
    if (!selectedFile) {
      return
    }

    if (!String(selectedFile.type || '').toLowerCase().startsWith('image/')) {
      setProfileModalError('Please upload a valid image file.')
      event.target.value = ''
      return
    }

    if (Number(selectedFile.size || 0) > 2 * 1024 * 1024) {
      setProfileModalError('Profile image must be 2MB or less.')
      event.target.value = ''
      return
    }

    try {
      const imageDataUrl = await readFileAsDataUrl(selectedFile)
      setProfileDraft((previous) => ({
        ...previous,
        profile_image_url: imageDataUrl,
      }))
      setProfileModalError('')
    } catch {
      setProfileModalError('Unable to process profile image. Please try another image.')
    } finally {
      event.target.value = ''
    }
  }

  const handleProfileCompletionSubmit = async (event) => {
    event.preventDefault()

    const payload = {
      name: String(profileDraft.name || '').trim(),
      phone: String(profileDraft.phone || '').trim(),
      city: String(profileDraft.city || '').trim(),
      vehicle_type: String(profileDraft.vehicle_type || '').trim(),
      profile_image_url: String(profileDraft.profile_image_url || '').trim(),
    }

    if (!payload.profile_image_url) {
      setProfileModalError('Add a profile image to complete your profile.')
      return
    }

    if (!payload.name || !payload.phone || !payload.city || !payload.vehicle_type) {
      setProfileModalError('Complete all profile fields before continuing.')
      return
    }

    setProfileModalSaving(true)
    setProfileModalError('')

    try {
      const response = await upsertProfile(payload)
      const normalized = normalizeProfileData(response?.data?.data)

      setProfileState({
        loading: false,
        data: normalized,
      })
      setProfileDraft(toProfileDraft(normalized))
      setProfileModalOpen(!normalized.is_complete)
      setProfileModalInfo(
        normalized.is_complete
          ? 'Profile completed successfully. You can now access all features.'
          : 'Profile saved as draft. Complete all fields to continue.',
      )
    } catch (requestError) {
      const detail = requestError?.response?.data?.detail
      setProfileModalError(typeof detail === 'string' ? detail : 'Unable to save profile right now.')
    } finally {
      setProfileModalSaving(false)
    }
  }

  const handleSidebarNavigate = (path) => {
    setProfileMenuOpen(false)
    navigate(path)
  }

  const handleLogout = () => {
    clearToken()
    setProfileMenuOpen(false)
    setActiveTriggerPopup(null)
    navigate('/login', { replace: true })
  }

  const capturePosition = (coords) => {
    const nextPosition = {
      lat: Number(coords.latitude),
      lng: Number(coords.longitude),
      timestamp: new Date().toISOString(),
    }

    latestPositionRef.current = nextPosition
    setLatestPosition(nextPosition)
    return nextPosition
  }

  const updateFromMonitorResponse = (response, fallbackPosition, syncMode = 'auto') => {
    const monitorData = response?.data?.data || {}
    const triggerList = Array.isArray(monitorData?.stored_triggers) ? monitorData.stored_triggers : []
    const triggerCount = triggerList.length

    if (triggerCount > 0) {
      setMonitorHint(`Monitoring active. ${triggerCount} new trigger(s) detected.`)

      const unseenTrigger = triggerList.find((trigger) => {
        const fingerprint = buildTriggerFingerprint(trigger)
        if (seenTriggerFingerprintsRef.current.has(fingerprint)) {
          return false
        }

        seenTriggerFingerprintsRef.current.add(fingerprint)
        return true
      })

      if (unseenTrigger) {
        const normalizedType = normalizeTriggerType(unseenTrigger?.trigger_type)
        const presentation = TRIGGER_PRESENTATION[normalizedType] || DEFAULT_TRIGGER_PRESENTATION
        const policyCandidates = Array.isArray(unseenTrigger?.policy_types)
          ? unseenTrigger.policy_types.filter((item) => Boolean(String(item || '').trim()))
          : []
        const resolvedClaimLocation = resolveClaimLocation(unseenTrigger, fallbackPosition)

        setLastDetectedTrigger({
          triggerType: normalizedType,
          timestamp: String(
            unseenTrigger?.timestamp || fallbackPosition?.timestamp || new Date().toISOString(),
          ),
          location: resolvedClaimLocation,
          policy: policyCandidates[0] || presentation.policy,
        })

        setActiveTriggerPopup({
          triggerType: normalizedType,
          disruption: presentation.disruption,
          policy: policyCandidates[0] || presentation.policy,
          eligiblePayout: presentation.eligiblePayout,
          claimContext: {
            user_location: resolvedClaimLocation,
            timestamp: String(
              unseenTrigger?.timestamp || fallbackPosition?.timestamp || new Date().toISOString(),
            ),
          },
        })
      }
      return
    }

    if (syncMode === 'manual') {
      setMonitorHint('Monitoring active. Manual sync completed.')
      return
    }

    setMonitorHint('Monitoring active. No new triggers right now.')
  }

  const requestLocationPermission = () => {
    if (!secureContext) {
      setPermissionState('unsupported')
      setMonitorHint('Location APIs require HTTPS or localhost. Open this app on localhost or HTTPS.')
      return
    }

    if (!geolocationSupported) {
      setPermissionState('unsupported')
      setMonitorHint('Geolocation is not supported in this browser.')
      return
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const currentPosition = capturePosition(position.coords)
        setPermissionState('granted')

        try {
          setMonitorState('sending')
          const response = await monitorLocation({
            lat: currentPosition.lat,
            lng: currentPosition.lng,
            timestamp: currentPosition.timestamp,
          })
          lastSentAtRef.current = Date.now()
          setLastSyncTimestamp(currentPosition.timestamp)
          setMonitorState('synced')
          updateFromMonitorResponse(response, currentPosition, 'manual')
        } catch (error) {
          const statusCode = error?.response?.status
          setMonitorState('error')
          if (statusCode === 401) {
            setMonitorHint('Session expired. Log in again to continue monitoring.')
          } else {
            setMonitorHint(
              statusCode
                ? `Location captured, but backend sync failed (HTTP ${statusCode}).`
                : 'Location captured, but backend sync failed. Check backend server status.',
            )
          }
        }
      },
      (error) => {
        if (error?.code === 1) {
          setPermissionState('denied')
          setMonitorHint('Location permission denied. Enable it from browser site settings.')
          return
        }

        if (error?.code === 3) {
          setMonitorHint('Location request timed out. Move to open sky and try again.')
          return
        }

        setMonitorHint('Unable to request location right now. Try again.')
      },
      {
        enableHighAccuracy: true,
        timeout: 20000,
        maximumAge: 0,
      },
    )
  }

  useEffect(() => {
    if (!geolocationSupported) {
      return undefined
    }

    const configuredInterval = Number(import.meta.env.VITE_MONITOR_INTERVAL_MS || DEFAULT_MONITOR_INTERVAL_MS)
    const monitorIntervalMs = Number.isFinite(configuredInterval)
      ? Math.max(30000, configuredInterval)
      : DEFAULT_MONITOR_INTERVAL_MS

    let disposed = false

    const pushLatestLocation = async () => {
      const latestPosition = latestPositionRef.current
      if (!latestPosition || disposed) {
        return
      }

      const nowMs = Date.now()
      if (nowMs - lastSentAtRef.current < 5000) {
        return
      }

      try {
        setMonitorState('sending')
        const response = await monitorLocation({
          lat: latestPosition.lat,
          lng: latestPosition.lng,
          timestamp: latestPosition.timestamp,
        })

        lastSentAtRef.current = nowMs
        setLastSyncTimestamp(latestPosition.timestamp)
        setMonitorState('synced')
        updateFromMonitorResponse(response, latestPosition)
      } catch {
        setMonitorState('error')
        setMonitorHint('Location captured, but sync to backend failed. Retrying automatically.')
        // Monitoring should be non-blocking for the user experience.
      }
    }

    let permissionStatus = null
    if (permissionsSupported) {
      const permissionsApi = navigator.permissions
      permissionsApi
        .query({ name: 'geolocation' })
        .then((result) => {
          if (disposed) {
            return
          }
          permissionStatus = result
          setPermissionState(result.state)
          result.onchange = () => {
            setPermissionState(result.state)
          }
        })
        .catch(() => {
          setPermissionState('prompt')
        })
    }

    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        capturePosition(position.coords)

        setMonitorState('watching')
        setPermissionState('granted')

        if (lastSentAtRef.current === 0) {
          void pushLatestLocation()
        }
      },
      (error) => {
        if (error?.code === 1) {
          setPermissionState('denied')
          setMonitorState('blocked')
          setMonitorHint('Location permission denied. Enable it from browser site settings.')
          return
        }

        setMonitorState('error')
        setMonitorHint('Unable to read location. Please keep location services enabled.')
      },
      {
        enableHighAccuracy: true,
        timeout: 20000,
        maximumAge: 30000,
      },
    )

    navigator.geolocation.getCurrentPosition(
      (position) => {
        capturePosition(position.coords)
        setPermissionState('granted')
        setMonitorState('watching')
        void pushLatestLocation()
      },
      (error) => {
        if (error?.code === 1) {
          setPermissionState('denied')
          setMonitorState('blocked')
          setMonitorHint('Location permission denied. Enable it from browser site settings.')
          return
        }

        if (error?.code === 3) {
          setMonitorState('idle')
          setMonitorHint('Waiting for GPS fix. Keep location enabled and stay on this page.')
        }
      },
      {
        enableHighAccuracy: false,
        timeout: 20000,
        maximumAge: 60000,
      },
    )

    const intervalId = window.setInterval(() => {
      void pushLatestLocation()
    }, monitorIntervalMs)

    return () => {
      disposed = true
      if (permissionStatus) {
        permissionStatus.onchange = null
      }
      window.clearInterval(intervalId)
      navigator.geolocation.clearWatch(watchId)
    }
  }, [geolocationSupported, permissionsSupported])

  const formattedSyncTime = lastSyncTimestamp
    ? new Date(lastSyncTimestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : ''

  const monitoringContextValue = {
    permissionState,
    monitorState,
    monitorHint,
    formattedSyncTime,
    lastSyncTimestamp,
    latestPosition,
    lastDetectedTrigger,
    requestLocationPermission,
    geolocationSupported,
    secureContext,
  }

  return (
    <div className="layout-shell">
      <Navbar
        showBack={showBack}
        onBack={handleBack}
        profileName={profileState?.data?.name}
        profileImageUrl={profileState?.data?.profile_image_url}
        onOpenProfileMenu={() => setProfileMenuOpen(true)}
      />
      <main className="layout-content">
        <Outlet context={monitoringContextValue} />
      </main>

      <button
        type="button"
        className={`layout-sidebar-backdrop ${profileMenuOpen ? 'is-open' : ''}`}
        aria-label="Close profile sidebar"
        onClick={() => setProfileMenuOpen(false)}
      />
      <aside
        className={`layout-sidebar ${profileMenuOpen ? 'is-open' : ''}`}
        aria-label="Profile sidebar"
      >
        <header className="layout-sidebar-header">
          <div className="layout-sidebar-avatar-wrap">
            {profileState?.data?.profile_image_url ? (
              <img
                src={profileState.data.profile_image_url}
                alt="Profile"
                className="layout-sidebar-avatar"
              />
            ) : (
              <span className="layout-sidebar-avatar-fallback" aria-hidden="true">
                {String(profileState?.data?.name || 'U')
                  .trim()
                  .charAt(0)
                  .toUpperCase()}
              </span>
            )}
          </div>
          <div className="layout-sidebar-user-meta">
            <h2>{profileState?.data?.name ? profileState.data.name : 'Your profile'}</h2>
            <p>{profileState?.loading ? 'Loading profile...' : 'Manage account and coverage'}</p>
          </div>
        </header>

        <nav className="layout-sidebar-nav" aria-label="Profile navigation">
          <p className="layout-sidebar-section-title">
            <LayoutDashboard size={14} strokeWidth={2.1} aria-hidden="true" />
            MAIN
          </p>

          <div className="layout-sidebar-menu-group">
            {profileSidebarItems.map((item) => {
              const ItemIcon = item.Icon

              return (
                <button
                  key={item.path}
                  type="button"
                  className={`layout-sidebar-item ${location.pathname === item.path ? 'is-active' : ''}`}
                  onClick={() => handleSidebarNavigate(item.path)}
                >
                  <span className="layout-sidebar-item-icon" aria-hidden="true">
                    <ItemIcon size={18} strokeWidth={2.1} />
                  </span>
                  <span className="layout-sidebar-item-label">{item.label}</span>
                  <span className="layout-sidebar-item-arrow" aria-hidden="true">
                    {'>'}
                  </span>
                </button>
              )
            })}
          </div>
        </nav>

        <button type="button" className="layout-sidebar-logout" onClick={handleLogout}>
          Logout
        </button>
      </aside>

      {profileModalOpen ? (
        <div className="layout-profile-modal-overlay" role="dialog" aria-modal="true">
          <article className="layout-profile-modal-card">
            <p className="layout-profile-modal-kicker">Complete your profile</p>
            <h2>Finish setup before using Covrly</h2>
            <p className="layout-profile-modal-copy">
              Add your profile details and photo once to unlock policy purchase, triggers, and claims.
            </p>

            <form className="layout-profile-modal-form" onSubmit={handleProfileCompletionSubmit}>
              <label className="layout-profile-image-uploader" htmlFor="layout-profile-image-input">
                {profileDraft.profile_image_url ? (
                  <img
                    src={profileDraft.profile_image_url}
                    alt="Profile preview"
                    className="layout-profile-image-preview"
                  />
                ) : (
                  <span className="layout-profile-image-placeholder" aria-hidden="true">
                    Upload Photo
                  </span>
                )}
              </label>
              <input
                id="layout-profile-image-input"
                type="file"
                accept="image/*"
                onChange={handleProfileImageChange}
                className="layout-profile-image-input"
              />

              <div className="layout-profile-grid">
                <label htmlFor="layout-profile-name">
                  Full Name
                  <input
                    id="layout-profile-name"
                    name="name"
                    type="text"
                    value={profileDraft.name}
                    onChange={handleProfileDraftChange}
                    autoComplete="name"
                    required
                  />
                </label>

                <label htmlFor="layout-profile-phone">
                  Phone
                  <input
                    id="layout-profile-phone"
                    name="phone"
                    type="tel"
                    value={profileDraft.phone}
                    onChange={handleProfileDraftChange}
                    autoComplete="tel"
                    required
                  />
                </label>

                <label htmlFor="layout-profile-city">
                  City
                  <input
                    id="layout-profile-city"
                    name="city"
                    type="text"
                    value={profileDraft.city}
                    onChange={handleProfileDraftChange}
                    autoComplete="address-level2"
                    required
                  />
                </label>

                <label htmlFor="layout-profile-vehicle-type">
                  Vehicle Type
                  <input
                    id="layout-profile-vehicle-type"
                    name="vehicle_type"
                    type="text"
                    value={profileDraft.vehicle_type}
                    onChange={handleProfileDraftChange}
                    placeholder="Car, bike, scooter"
                    required
                  />
                </label>
              </div>

              {profileModalError ? (
                <p className="layout-profile-modal-feedback layout-profile-modal-feedback-error">
                  {profileModalError}
                </p>
              ) : null}
              {profileModalInfo ? (
                <p className="layout-profile-modal-feedback layout-profile-modal-feedback-success">
                  {profileModalInfo}
                </p>
              ) : null}

              <div className="layout-profile-modal-actions">
                <button type="submit" disabled={profileModalSaving}>
                  {profileModalSaving ? 'Saving profile...' : 'Complete profile'}
                </button>
                <button
                  type="button"
                  className="layout-profile-modal-logout"
                  onClick={handleLogout}
                  disabled={profileModalSaving}
                >
                  Logout
                </button>
              </div>
            </form>
          </article>
        </div>
      ) : null}

      <TriggerPopup
        isOpen={Boolean(activeTriggerPopup)}
        disruption={activeTriggerPopup?.disruption}
        policy={activeTriggerPopup?.policy}
        eligiblePayout={activeTriggerPopup?.eligiblePayout}
        triggerType={activeTriggerPopup?.triggerType}
        claimContext={activeTriggerPopup?.claimContext}
        onClose={() => setActiveTriggerPopup(null)}
        onClaimSuccess={() => {
          setMonitorHint('Trigger claim submitted successfully.')
          setActiveTriggerPopup(null)
        }}
        onClaimError={(message) => {
          setMonitorHint(typeof message === 'string' ? message : 'Unable to submit trigger claim.')
        }}
      />
      <BottomNav />
    </div>
  )
}

export default Layout
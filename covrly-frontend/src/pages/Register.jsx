import { useRef, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { isAuthenticated, registerUser, requestRegisterOtp } from '../services/api'
import './Register.css'

const initialFormData = {
  email: '',
  password: '',
  confirmPassword: '',
  otp: '',
}

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

const maskEmail = (rawEmail) => {
  const normalized = String(rawEmail || '').trim().toLowerCase()
  if (!normalized.includes('@')) {
    return normalized
  }

  const [localPart, domainPart] = normalized.split('@')
  const domainSegments = String(domainPart || '').split('.')
  const domainName = domainSegments[0] || ''
  const tld = domainSegments.slice(1).join('.')

  const maskToken = (token) => {
    const value = String(token || '')
    if (value.length <= 2) {
      return `${value.charAt(0) || ''}*`
    }
    return `${value.charAt(0)}${'*'.repeat(Math.min(4, value.length - 2))}${value.charAt(value.length - 1)}`
  }

  const maskedLocal = maskToken(localPart)
  const maskedDomain = maskToken(domainName)
  return tld ? `${maskedLocal}@${maskedDomain}.${tld}` : `${maskedLocal}@${maskedDomain}`
}

function Register() {
  const [formData, setFormData] = useState(initialFormData)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(false)
  const [otpSending, setOtpSending] = useState(false)
  const [otpSent, setOtpSent] = useState(false)
  const [maskedOtpEmail, setMaskedOtpEmail] = useState('')
  const otpInputRef = useRef(null)

  const navigate = useNavigate()

  if (isAuthenticated()) {
    return <Navigate to="/dashboard" replace />
  }

  const handleInputChange = (event) => {
    const { name, value } = event.target
    const nextValue =
      name === 'otp'
        ? String(value || '')
            .replace(/\D/g, '')
            .slice(0, 6)
        : value

    setFormData((prev) => ({
      ...prev,
      [name]: nextValue,
    }))

    if (name === 'email' && otpSent) {
      setOtpSent(false)
      setMaskedOtpEmail('')
    }

    if (error) {
      setError('')
    }

    if (info) {
      setInfo('')
    }
  }

  const handleRequestOtp = async () => {
    const email = String(formData.email || '').trim().toLowerCase()

    if (!EMAIL_PATTERN.test(email)) {
      setError('Enter a valid email before requesting OTP.')
      return
    }

    setOtpSending(true)
    setError('')
    setInfo('')

    try {
      const response = await requestRegisterOtp({ email })
      const expiryMinutes = Number(response?.data?.data?.expires_in_minutes || 10)
      setOtpSent(true)
      setMaskedOtpEmail(maskEmail(email))
      setInfo(`OTP sent. It expires in ${expiryMinutes} minutes.`)

      if (otpInputRef.current) {
        otpInputRef.current.focus()
        otpInputRef.current.select()
      }
    } catch (requestError) {
      const detail = requestError?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Unable to send OTP right now.')
    } finally {
      setOtpSending(false)
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()

    const email = String(formData.email || '').trim().toLowerCase()

    if (!EMAIL_PATTERN.test(email)) {
      setError('Enter a valid email address.')
      return
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    if (!String(formData.otp || '').trim()) {
      setError('Enter the OTP sent to your email.')
      return
    }

    setLoading(true)
    setError('')
    setInfo('')

    try {
      await registerUser({
        email,
        password: formData.password,
        otp: String(formData.otp || '').trim(),
      })
      navigate('/login', { replace: true, state: { registered: true } })
    } catch (requestError) {
      const detail = requestError?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Unable to register right now.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="register-page" aria-label="Register page">
      <div className="register-card">
        <header className="register-header">
          <p className="register-eyebrow">Create Account</p>
          <h1>Join Covrly</h1>
        </header>

        <form className="register-form" onSubmit={handleSubmit}>
          <label htmlFor="register-email">Email</label>
          <div className="register-email-row">
            <input
              id="register-email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="Enter your email address"
              value={formData.email}
              onChange={handleInputChange}
              required
            />
            <button
              type="button"
              className="register-button register-button-secondary"
              onClick={handleRequestOtp}
              disabled={otpSending}
            >
              {otpSending ? 'Sending...' : otpSent ? 'Resend OTP' : 'Send OTP'}
            </button>
          </div>

          <label htmlFor="register-otp">Email OTP</label>
          <input
            id="register-otp"
            name="otp"
            ref={otpInputRef}
            inputMode="numeric"
            pattern="[0-9]*"
            autoComplete="one-time-code"
            placeholder="Enter 6-digit OTP"
            minLength={6}
            maxLength={6}
            value={formData.otp}
            onChange={handleInputChange}
            required
          />
          {otpSent && maskedOtpEmail ? (
            <p className="register-otp-destination" aria-live="polite">
              Code sent to {maskedOtpEmail}
            </p>
          ) : null}

          <label htmlFor="register-password">Password</label>
          <input
            id="register-password"
            name="password"
            type="password"
            autoComplete="new-password"
            placeholder="At least 6 characters"
            minLength={6}
            value={formData.password}
            onChange={handleInputChange}
            required
          />

          <label htmlFor="register-confirm-password">Confirm Password</label>
          <input
            id="register-confirm-password"
            name="confirmPassword"
            type="password"
            autoComplete="new-password"
            placeholder="Re-enter your password"
            minLength={6}
            value={formData.confirmPassword}
            onChange={handleInputChange}
            required
          />

          {info ? <p className="register-feedback register-feedback-info">{info}</p> : null}
          {error ? <p className="register-feedback register-feedback-error">{error}</p> : null}

          <button type="submit" className="register-button register-button-primary" disabled={loading}>
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <div className="register-links" aria-label="Register helper links">
          <span>Already have an account?</span>
          <Link to="/login">Sign in</Link>
        </div>
      </div>
    </section>
  )
}

export default Register

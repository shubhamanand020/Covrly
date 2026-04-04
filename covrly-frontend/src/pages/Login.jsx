import { useState } from 'react'
import './Login.css'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { isAuthenticated, loginUser, setToken } from '../services/api'

const initialFormData = {
  email: '',
  password: '',
}

function Login() {
  const [formData, setFormData] = useState(initialFormData)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const navigate = useNavigate()
  const location = useLocation()

  const redirectedFrom =
    typeof location.state?.from === 'string' && location.state.from ? location.state.from : '/dashboard'

  if (isAuthenticated()) {
    return <Navigate to="/dashboard" replace />
  }

  const handleInputChange = (event) => {
    const { name, value } = event.target

    setFormData((previousData) => ({
      ...previousData,
      [name]: value,
    }))

    if (error) {
      setError('')
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()

    setLoading(true)
    setError('')

    try {
      const response = await loginUser({
        email: String(formData.email || '').trim(),
        password: formData.password,
      })

      const token = response?.data?.data?.token
      if (!token) {
        setError('Login failed: missing token from server response.')
        return
      }

      setToken(token)
      navigate(redirectedFrom, { replace: true })
    } catch (requestError) {
      const detail = requestError?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Invalid credentials. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="login-page" aria-label="Login page">
      <div className="login-card">
        <header className="login-header">
          <p className="login-eyebrow">Welcome Back</p>
          <h1>Sign in to Covrly</h1>
        </header>

        <form className="login-form" onSubmit={handleSubmit}>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            placeholder="Enter your email address"
            value={formData.email}
            onChange={handleInputChange}
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            placeholder="Enter your password"
            value={formData.password}
            onChange={handleInputChange}
            required
          />

          {error ? <p className="login-feedback login-feedback-error">{error}</p> : null}

          <button type="submit" className="login-button login-button-primary" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="login-links" aria-label="Login helper links">
          <span>New to Covrly?</span>
          <Link to="/register">Create account</Link>
        </div>
      </div>
    </section>
  )
}

export default Login
import axios from 'axios'

const TOKEN_STORAGE_KEY = 'covrly_auth_token'
const API_BASE_URL = 'https://covrly.onrender.com'
const API_TIMEOUT_MS = 30000
const RETRY_DELAY_MS = 1000

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT_MS,
})

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const shouldRetryRequest = (requestError) =>
  requestError?.code === 'ECONNABORTED' || !requestError?.response

const runWithSingleRetry = async (requestFactory) => {
  try {
    return await requestFactory()
  } catch (requestError) {
    if (!shouldRetryRequest(requestError)) {
      throw requestError
    }

    await delay(RETRY_DELAY_MS)
    return requestFactory()
  }
}

let warmupRequest = null

export const warmup = () => {
  if (!warmupRequest) {
    warmupRequest = api.get('/').catch(() => null)
  }
  return warmupRequest
}

export const getApiErrorMessage = (requestError, fallbackMessage = 'Something went wrong.') => {
  const detail = requestError?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }

  if (Array.isArray(detail)) {
    const validationMessage = detail
      .map((item) => item?.msg)
      .filter((msg) => typeof msg === 'string' && msg.trim())
      .join(', ')
    if (validationMessage) {
      return validationMessage
    }
  }

  if (requestError?.code === 'ECONNABORTED') {
    return 'Server is waking up. Please wait a few seconds and try again.'
  }

  if (!requestError?.response) {
    return 'Network error. Please check your connection and try again.'
  }

  if (Number(requestError?.response?.status) >= 500) {
    return 'Server error. Please try again shortly.'
  }

  const message = requestError?.message
  if (!requestError?.response && typeof message === 'string' && message.trim()) {
    return `Cannot reach backend API. ${message.trim()}`
  }

  return fallbackMessage
}

export const getToken = () => localStorage.getItem(TOKEN_STORAGE_KEY)

export const setToken = (token) => {
  const normalizedToken = typeof token === 'string' ? token.trim() : ''
  if (!normalizedToken) {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    return
  }
  localStorage.setItem(TOKEN_STORAGE_KEY, normalizedToken)
}

export const clearToken = () => {
  localStorage.removeItem(TOKEN_STORAGE_KEY)
}

export const isAuthenticated = () => Boolean(getToken())

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const registerUser = (data) => api.post('/auth/register', data)

export const sendOtp = async (data) => {
  const response = await runWithSingleRetry(() =>
    api.post('/auth/register/request-otp', data),
  )
  return response.data
}

export const requestRegisterOtp = sendOtp

export const loginUser = (data) => api.post('/auth/login', data)

export const getProfile = () => api.get('/profile')

export const upsertProfile = (data) => api.post('/profile', data)

export const buyPolicy = (data) => api.post('/policies/buy', data)

export const getMyPolicies = () => api.get('/policies/my')

export const monitorLocation = (data) => api.post('/monitor/location', data)

export const getMyTriggers = () => api.get('/monitor/my-triggers')

export const submitManualClaim = (data) => api.post('/claim/manual', data)

export const triggerAutoFlow = (data) => api.post('/auto/trigger', data)

export const verifyAutoFlow = (data) => api.post('/auto/verify', data)

// Legacy aliases retained for older callers.
export const submitClaim = (data) => submitManualClaim(data)

export const verifyClaim = (data) => verifyAutoFlow(data)

export const checkTrigger = (params) =>
  triggerAutoFlow({
    user_location: {
      lat: Number(params?.latitude ?? 12.97),
      lng: Number(params?.longitude ?? 77.59),
    },
    timestamp: params?.timestamp,
  })

export const getPolicies = () => api.get('/policies')

export const calculatePremium = (params) => api.get('/premium/calculate', { params })

export default api
import axios from 'axios'

const TOKEN_STORAGE_KEY = 'covrly_auth_token'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000,
})

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

export const requestRegisterOtp = (data) => api.post('/auth/register/request-otp', data)

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
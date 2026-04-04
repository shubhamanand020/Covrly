import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import ManualClaimPage from './pages/ManualClaimPage'
import AutoFlowHandler from './pages/AutoFlowHandler'
import Policy from './pages/Policy'
import Tracking from './pages/Tracking'
import Payout from './pages/Payout'
import Verification from './pages/Verification'
import Profile from './pages/Profile'
import Settings from './pages/Settings'
import Plans from './pages/Plans'
import LocationPage from './pages/LocationPage'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import './styles/app.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/claim" element={<Navigate to="/claim/manual" replace />} />
            <Route path="/claim/manual" element={<ManualClaimPage />} />
            <Route path="/auto-flow" element={<AutoFlowHandler />} />
            <Route path="/policy" element={<Policy />} />
            <Route path="/tracking" element={<Tracking />} />
            <Route path="/payout" element={<Payout />} />
            <Route path="/verification" element={<Verification />} />
            <Route path="/location" element={<LocationPage />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/plans" element={<Plans />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App

import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'

export default function ProtectedRoute() {
  const { token, user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="grid min-h-screen place-items-center text-sm text-slate-500">Loading your account…</div>
  if (!token || !user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

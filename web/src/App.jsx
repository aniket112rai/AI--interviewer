import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth/AuthContext.jsx'
import ProtectedRoute from './auth/ProtectedRoute.jsx'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Login from './pages/Login.jsx'
import Signup from './pages/Signup.jsx'
import VoiceLoop from './pages/VoiceLoop.jsx'
import UploadResume from './pages/UploadResume.jsx'
import NewInterview from './pages/NewInterview.jsx'
import PostInterview from './pages/PostInterview.jsx'

function HomeRedirect() {
  const { token, loading } = useAuth()
  if (loading) return <div className="grid min-h-screen place-items-center text-sm text-slate-500">Loading…</div>
  return <Navigate to={token ? '/dashboard' : '/login'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/upload-resume" element={<UploadResume />} />
          <Route path="/sessions/new" element={<NewInterview />} />
          <Route path="/sessions/:sessionId/live" element={<VoiceLoop />} />
          <Route path="/sessions/:sessionId/report" element={<PostInterview />} />
        </Route>
      </Route>
      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  )
}

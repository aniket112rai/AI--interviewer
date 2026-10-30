import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiRequest, registerUnauthorizedHandler } from '../api/client.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const navigate = useNavigate()
  const [token, setToken] = useState(false)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback((redirect = true) => {
    apiRequest('/api/auth/logout', { method: 'POST' }).catch(() => {})
    setToken(null)
    setUser(null)
    setLoading(false)
    if (redirect) navigate('/login', { replace: true })
  }, [navigate])

  useEffect(() => registerUnauthorizedHandler(() => logout(true)), [logout])

  useEffect(() => {
    let active = true
    apiRequest('/api/auth/me')
      .then((currentUser) => { if (active) setUser(currentUser) })
      .catch(() => { if (active) logout(false) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [logout])

  const acceptSession = useCallback((userData) => {
    setToken(true)
    setUser(userData)
    setLoading(false)
  }, [])

  const value = useMemo(() => ({ token, user, loading, acceptSession, logout }), [token, user, loading, acceptSession, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider.')
  return value
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

let onUnauthorized = () => {}

export function registerUnauthorizedHandler(handler) {
  onUnauthorized = handler
  return () => {
    if (onUnauthorized === handler) onUnauthorized = () => {}
  }
}

export async function apiRequest(path, options = {}) {
  const token = localStorage.getItem('token')
  const headers = new Headers(options.headers || {})
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  if (response.status === 401 && token && !path.startsWith('/api/auth/login') && !path.startsWith('/api/auth/signup')) {
    onUnauthorized()
  }
  const data = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) {
    const error = new Error(data?.detail || 'The request could not be completed.')
    error.status = response.status
    throw error
  }
  return data
}

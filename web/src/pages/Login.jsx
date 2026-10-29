import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { apiRequest } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { token, acceptSession } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  if (token) return <Navigate to="/dashboard" replace />

  async function submit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const session = await apiRequest('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
      acceptSession(session)
      navigate(location.state?.from || '/dashboard', { replace: true })
    } catch (cause) {
      setError(cause.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[#f6f5f1] px-5 py-12">
      <section className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-sm sm:p-10">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-600">AI Interviewer</p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight">Welcome back</h1>
        <p className="mt-2 text-sm text-slate-600">Log in to continue your interview practice.</p>
        <form onSubmit={submit} className="mt-8 space-y-5">
          <label className="block text-sm font-medium">Email<input autoComplete="email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100" /></label>
          <label className="block text-sm font-medium">Password<input autoComplete="current-password" type="password" required value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100" /></label>
          {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
          <button disabled={submitting} className="w-full rounded-full bg-indigo-600 px-5 py-3 font-semibold text-white hover:bg-indigo-700 disabled:opacity-60">{submitting ? 'Logging in…' : 'Log in'}</button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600">New here? <Link to="/signup" className="font-semibold text-indigo-700">Create an account</Link></p>
      </section>
    </main>
  )
}

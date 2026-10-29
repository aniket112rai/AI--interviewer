import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiRequest } from '../api/client.js'
import { usePolling } from '../hooks/usePolling.js'

const levels = ['intern', 'junior', 'mid', 'senior']

export default function NewInterview() {
  const navigate = useNavigate()
  const [resumes, setResumes] = useState([])
  const [resumeId, setResumeId] = useState('')
  const [level, setLevel] = useState('junior')
  const [duration, setDuration] = useState(15)
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    apiRequest('/api/resumes')
      .then(async (items) => {
        const ready = items.filter((item) => item.status === 'ready')
        if (!active) return
        setResumes(ready)
        if (ready.length) {
          setResumeId(ready[0].id)
          const detail = await apiRequest(`/api/resumes/${ready[0].id}`)
          if (active) setLevel(levels.includes(detail.profile?.seniority) ? detail.profile.seniority : 'junior')
        }
      })
      .catch((cause) => { if (active) setError(cause.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  async function selectResume(id) {
    setResumeId(id)
    try {
      const detail = await apiRequest(`/api/resumes/${id}`)
      setLevel(levels.includes(detail.profile?.seniority) ? detail.profile.seniority : 'junior')
    } catch (cause) {
      setError(cause.message)
    }
  }

  async function createInterview(event) {
    event.preventDefault()
    setCreating(true)
    setError('')
    setSession(null)
    try {
      const result = await apiRequest('/api/sessions', {
        method: 'POST',
        body: JSON.stringify({ resume_id: resumeId, level, duration_min: Number(duration) }),
      })
      const detail = await apiRequest(`/api/sessions/${result.id}`)
      setSession(detail)
    } catch (cause) {
      setError(cause.message)
    } finally {
      setCreating(false)
    }
  }

  const refreshSession = useCallback(async () => {
    if (!session?.id) return
    try {
      setSession(await apiRequest(`/api/sessions/${session.id}`))
    } catch (cause) {
      setError(cause.message)
    }
  }, [session?.id])
  usePolling(refreshSession, session?.status === 'planning' ? 1500 : null,
    () => !session || session.status !== 'planning')

  if (loading) return <p className="text-sm text-slate-500">Loading resumes…</p>

  return (
    <div className="mx-auto max-w-2xl">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-600">Resume-based practice</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">Prepare an interview</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">Choose a ready resume, then set the level and time. Your plan is tailored to the projects and experience in that profile.</p>

      {resumes.length === 0 ? (
        <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-7">
          <p className="text-slate-700">Upload and process a resume before starting an interview.</p>
          <Link to="/upload-resume" className="mt-5 inline-flex rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700">Upload a resume</Link>
        </section>
      ) : (
        <form onSubmit={createInterview} className="mt-8 space-y-6 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">
          <label className="block text-sm font-medium text-slate-700">Resume
            <select value={resumeId} onChange={(event) => selectResume(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3">
              {resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.filename}</option>)}
            </select>
          </label>
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700">Interview level
              <select value={level} onChange={(event) => setLevel(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3">
                {levels.map((item) => <option key={item} value={item} className="capitalize">{item}</option>)}
              </select>
            </label>
            <label className="block text-sm font-medium text-slate-700">Duration
              <select value={duration} onChange={(event) => setDuration(Number(event.target.value))} className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3">
                {[15, 30, 45].map((minutes) => <option key={minutes} value={minutes}>{minutes} minutes</option>)}
              </select>
            </label>
          </div>
          <button disabled={creating || !resumeId} className="rounded-full bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-wait disabled:opacity-60">
            {creating ? 'Creating plan…' : 'Create interview plan'}
          </button>
        </form>
      )}

      {session?.status === 'planning' && <p role="status" className="mt-6 rounded-2xl bg-indigo-50 p-5 text-sm font-medium text-indigo-800">Preparing your interview…</p>}
      {session?.status === 'failed' && <p role="alert" className="mt-6 rounded-2xl bg-rose-50 p-5 text-sm text-rose-800">{session.error || 'We could not prepare this interview. Please try again.'}</p>}
      {session?.status === 'ready' && <section className="mt-6 rounded-3xl border border-emerald-200 bg-white p-7">
        <p className="text-sm font-semibold text-emerald-700">Your interview is ready</p>
        <ul className="mt-4 list-inside list-disc space-y-2 text-sm text-slate-700">
          {session.topics.map((topic, index) => <li key={`${index}-${topic}`}>{topic}</li>)}
        </ul>
        <button onClick={() => navigate(`/sessions/${session.id}/live`)} className="mt-6 rounded-full bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700">Start interview</button>
      </section>}
      {error && <p role="alert" className="mt-5 text-sm text-rose-700">{error}</p>}
    </div>
  )
}

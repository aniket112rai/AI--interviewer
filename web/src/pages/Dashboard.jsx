import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'
import { usePolling } from '../hooks/usePolling.js'

function StatusBadge({ status }) {
  const styles = {
    ready: 'bg-emerald-50 text-emerald-700',
    completed: 'bg-emerald-50 text-emerald-700',
    failed: 'bg-rose-50 text-rose-700',
    live: 'bg-indigo-50 text-indigo-700',
    parsing: 'bg-amber-50 text-amber-700',
    planning: 'bg-amber-50 text-amber-700',
  }
  return <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold capitalize ${styles[status] || 'bg-slate-100 text-slate-600'}`}>{status}</span>
}

function ActionLink({ to, children, secondary = false, className = '' }) {
  return <Link to={to} className={`inline-flex min-h-11 items-center justify-center rounded-full px-5 py-2.5 text-sm font-semibold transition-colors ${secondary ? 'border border-slate-300 bg-white text-slate-800 hover:bg-slate-50' : 'bg-indigo-600 text-white hover:bg-indigo-700'} ${className}`}>{children}</Link>
}

export default function Dashboard() {
  const { user } = useAuth()
  const [resumes, setResumes] = useState([])
  const [sessions, setSessions] = useState([])
  const [resumeLoading, setResumeLoading] = useState(true)
  const [sessionLoading, setSessionLoading] = useState(true)
  const [resumeError, setResumeError] = useState('')
  const [sessionError, setSessionError] = useState('')
  const [usage, setUsage] = useState(null)
  const [usageError, setUsageError] = useState('')

  const refreshResumes = useCallback(async () => {
    try {
      setResumes(await apiRequest('/api/resumes'))
      setResumeError('')
    } catch (cause) {
      setResumeError(cause.message)
    } finally {
      setResumeLoading(false)
    }
  }, [])

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await apiRequest('/api/sessions'))
      setSessionError('')
    } catch (cause) {
      setSessionError(cause.message)
    } finally {
      setSessionLoading(false)
    }
  }, [])

  useEffect(() => { refreshResumes(); refreshSessions() }, [refreshResumes, refreshSessions])
  useEffect(() => {
    let active = true
    apiRequest('/api/auth/me')
      .then((currentUser) => { if (active) setUsage(currentUser) })
      .catch((cause) => { if (active) setUsageError(cause.message) })
    return () => { active = false }
  }, [])
  const parsingResumes = resumes.some((resume) => resume.status === 'parsing')
  const preparingSessions = sessions.some((session) => session.status === 'planning')
  const pendingReports = sessions.some((session) => session.status === 'completed' && session.report_status === 'pending')
  usePolling(refreshResumes, parsingResumes ? 2500 : null, () => !parsingResumes)
  usePolling(refreshSessions, preparingSessions || pendingReports ? 2500 : null,
    () => !preparingSessions && !pendingReports)

  return (
    <div className="mx-auto max-w-5xl">
      <section className="rounded-3xl bg-slate-950 px-6 py-8 text-white shadow-sm sm:px-9 sm:py-10">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-300">Your practice space</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Welcome, {user?.name || 'candidate'}.</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-300">Practice with voice interviews built from your resume, then get specific feedback on your answers.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <ActionLink to="/upload-resume" secondary>Upload resume</ActionLink>
            <ActionLink to="/sessions/new">Start interview</ActionLink>
          </div>
        </div>
        <div className="mt-7 inline-flex rounded-2xl border border-white/15 bg-white/5 px-4 py-3 text-sm text-slate-200">
          Minutes used today <strong className="ml-2 text-white">{usage?.minutes_used ?? user?.minutes_used ?? 0} / {usage?.daily_minutes_limit ?? user?.daily_minutes_limit ?? '…'}</strong>
        </div>
        {usageError && <p role="status" className="mt-2 text-xs text-slate-300">Today’s usage is temporarily unavailable.</p>}
      </section>

      <section className="mt-7 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><h2 className="text-xl font-semibold">Your resumes</h2><p className="mt-1 text-sm text-slate-600">Profiles ready for a resume-based interview.</p></div>
          <ActionLink to="/upload-resume" secondary>Upload resume</ActionLink>
        </div>
        {resumeLoading && <p role="status" className="mt-6 rounded-2xl bg-slate-50 p-5 text-sm text-slate-600">Loading resumes…</p>}
        {resumeError && <div className="mt-5 rounded-2xl bg-rose-50 p-5 text-sm text-rose-800"><p role="alert">{resumeError}</p><button onClick={refreshResumes} className="mt-3 font-semibold underline">Try again</button></div>}
        {!resumeLoading && !resumeError && resumes.length === 0 && <div className="mt-6 rounded-2xl border border-dashed border-slate-300 p-6 text-center"><p className="font-medium text-slate-800">No resumes yet</p><p className="mt-1 text-sm text-slate-600">Upload a PDF or DOCX to create your interview profile.</p><ActionLink to="/upload-resume" className="mt-4">Upload your first resume</ActionLink></div>}
        {!resumeError && resumes.length > 0 && <ul className="mt-5 divide-y divide-slate-100">{resumes.map((resume) => (
          <li key={resume.id} className="flex flex-col gap-2 py-4 first:pt-0 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0"><p className="break-words font-medium text-slate-900">{resume.filename}</p>{resume.summary && <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">{resume.summary}</p>}{resume.error && <p className="mt-1 text-sm text-rose-700">{resume.error}</p>}</div>
            <StatusBadge status={resume.status} />
          </li>
        ))}</ul>}
      </section>

      <section className="mt-7 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><h2 className="text-xl font-semibold">Interview history</h2><p className="mt-1 text-sm text-slate-600">Plans, completed sessions, and feedback reports.</p></div>
          <ActionLink to="/sessions/new" secondary>Start interview</ActionLink>
        </div>
        {sessionLoading && <p role="status" className="mt-6 rounded-2xl bg-slate-50 p-5 text-sm text-slate-600">Loading interview history…</p>}
        {sessionError && <div className="mt-5 rounded-2xl bg-rose-50 p-5 text-sm text-rose-800"><p role="alert">{sessionError}</p><button onClick={refreshSessions} className="mt-3 font-semibold underline">Try again</button></div>}
        {!sessionLoading && !sessionError && sessions.length === 0 && <p className="mt-6 rounded-2xl bg-slate-50 p-5 text-sm text-slate-600">No interviews yet. Start one when your resume is ready.</p>}
        {!sessionError && sessions.length > 0 && <ul className="mt-5 divide-y divide-slate-100">{sessions.map((session) => (
          <li key={session.id} className="flex flex-col gap-4 py-5 first:pt-0 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="break-words font-semibold text-slate-900">{session.resume_filename || 'Resume removed'}</p>
              <p className="mt-1 text-sm text-slate-600"><time dateTime={session.created_at}>{new Date(session.created_at).toLocaleString()}</time> · <span className="capitalize">{session.level}</span> · {session.duration_min} minutes</p>
              {session.overall_score !== null && <p className="mt-2 text-sm font-medium text-indigo-700">Overall score: {session.overall_score}/100</p>}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge status={session.status} />
              {session.status === 'ready' && <Link to={`/sessions/${session.id}/live`} className="inline-flex min-h-11 items-center font-semibold text-indigo-700 hover:text-indigo-900">Start</Link>}
              {session.status === 'completed' && <Link to={`/sessions/${session.id}/report`} className="inline-flex min-h-11 items-center font-semibold text-indigo-700 hover:text-indigo-900">{session.report_status === 'ready' ? 'View report' : session.report_status === 'failed' ? 'Report unavailable' : 'View report'}</Link>}
            </div>
          </li>
        ))}</ul>}
      </section>
    </div>
  )
}

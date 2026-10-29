import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../api/client.js'
import { usePolling } from '../hooks/usePolling.js'

function StatusBadge({ status }) {
  const style = status === 'ready'
    ? 'bg-emerald-50 text-emerald-700'
    : status === 'failed'
      ? 'bg-rose-50 text-rose-700'
      : 'bg-amber-50 text-amber-700'
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${style}`}>{status}</span>
}

export default function UploadResume() {
  const [file, setFile] = useState(null)
  const [resume, setResume] = useState(null)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)

  const pollResume = useCallback(async () => {
    if (!resume?.id) return
    try {
      setResume(await apiRequest(`/api/resumes/${resume.id}`))
    } catch (cause) {
      setError(cause.message)
    }
  }, [resume?.id])

  usePolling(pollResume, resume?.status === 'parsing' ? 1400 : null,
    () => !resume || resume.status !== 'parsing')

  async function submit(event) {
    event.preventDefault()
    if (!file) return
    const form = event.currentTarget
    setError('')
    setResume(null)
    setUploading(true)
    try {
      const body = new FormData()
      body.append('file', file)
      const started = await apiRequest('/api/resumes', { method: 'POST', body })
      setResume({ id: started.id, status: started.status, filename: file.name })
      setFile(null)
      form.reset()
    } catch (cause) {
      setError(cause.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/dashboard" className="text-sm font-semibold text-indigo-700 hover:text-indigo-900">← Back to dashboard</Link>
      <section className="mt-5 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-600">Resume profile</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">Upload your resume</h1>
        <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600">Upload a text-based PDF or DOCX. We extract career details for interview practice and remove contact details before profile extraction.</p>
        <form onSubmit={submit} className="mt-7 space-y-4">
          <label className="block text-sm font-medium">Resume file
            <input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required onChange={(event) => setFile(event.target.files?.[0] || null)} className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm file:mr-4 file:rounded-full file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:font-semibold file:text-indigo-700" />
          </label>
          <p className="text-xs text-slate-500">PDF or DOCX · Maximum {import.meta.env.VITE_MAX_UPLOAD_MB || 5} MB</p>
          {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
          <button disabled={!file || uploading} className="rounded-full bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">{uploading ? 'Uploading…' : 'Upload resume'}</button>
        </form>
      </section>

      {resume && <section aria-live="polite" className="mt-6 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">{resume.filename || file?.name || 'Resume profile'}</h2>
          <StatusBadge status={resume.status} />
        </div>
        {resume.status === 'parsing' && <p className="mt-4 text-sm text-slate-600">Reading your resume and preparing your profile…</p>}
        {resume.status === 'failed' && <p role="alert" className="mt-4 text-sm leading-6 text-rose-700">{resume.error || 'We could not process this resume. Please try another PDF or DOCX file.'}</p>}
        {resume.status === 'ready' && resume.profile && <>
          <p className="mt-4 text-sm leading-6 text-slate-700">{resume.profile.summary}</p>
          <h3 className="mt-6 text-sm font-semibold">Skills found</h3>
          <div className="mt-3 flex flex-wrap gap-2">{resume.profile.skills.map((skill) => <span key={skill} className="rounded-full bg-slate-100 px-3 py-1.5 text-sm text-slate-700">{skill}</span>)}</div>
          {resume.profile.probe_targets.length > 0 && <>
            <h3 className="mt-6 text-sm font-semibold">Interviewers will verify</h3>
            <ul className="mt-2 list-inside list-disc space-y-1 text-sm leading-6 text-slate-600">{resume.profile.probe_targets.map((target, index) => <li key={`${index}-${target}`}>{target}</li>)}</ul>
          </>}
          <p className="mt-6 text-xs leading-5 text-slate-500">Review the summary and skills to confirm your resume was read correctly.</p>
          <Link to="/dashboard" className="mt-5 inline-flex rounded-full border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Done</Link>
        </>}
      </section>}
    </div>
  )
}

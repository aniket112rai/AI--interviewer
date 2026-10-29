import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiRequest } from '../api/client.js'
import { usePolling } from '../hooks/usePolling.js'
import ScoreBar from '../components/ScoreBar.jsx'

export default function PostInterview() {
  const { sessionId } = useParams()
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loadFailed, setLoadFailed] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const refresh = useCallback(async () => {
    try {
      const data = await apiRequest(`/api/sessions/${sessionId}/report`)
      setResult(data)
      setError('')
      setLoadFailed(false)
    } catch (cause) {
      if (cause.status === 409) {
        setResult({ session_id: sessionId, status: 'pending', report: null })
        setError('The interview is still finishing. Checking again shortly…')
        setLoadFailed(false)
        return
      }
      setError(cause.message)
      setLoadFailed(true)
    }
  }, [sessionId, refreshKey])

  useEffect(() => { refresh() }, [refresh])
  usePolling(refresh, !loadFailed && (result?.status === 'pending' || !result) ? 2500 : null,
    () => loadFailed || result?.status === 'ready' || result?.status === 'failed')

  const report = result?.report
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-700">Interview complete</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">Your interview feedback</h1>
        <p className="mt-2 text-sm text-slate-600">A practical review of your answers, based on this conversation.</p>
      </div>

      {error && <p role={loadFailed ? 'alert' : 'status'} className={`rounded-2xl p-4 text-sm ${loadFailed ? 'bg-rose-50 text-rose-800' : 'bg-amber-50 text-amber-900'}`}>{error}</p>}

      {loadFailed && <section className="rounded-3xl border border-rose-200 bg-white p-8 shadow-sm"><h2 className="text-lg font-semibold">Couldn’t load your report</h2><p className="mt-2 text-sm text-slate-600">Check your connection, then try again.</p><button type="button" onClick={() => { setError(''); setLoadFailed(false); setResult(null); setRefreshKey((key) => key + 1) }} className="mt-5 rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white">Try again</button></section>}

      {(!loadFailed && (!result || result.status === 'pending')) && (
        <section aria-live="polite" className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex items-center gap-3"><span className="h-3 w-3 animate-pulse rounded-full bg-indigo-600" /><h2 className="font-semibold">Preparing your report…</h2></div>
          <p className="mt-3 text-sm leading-6 text-slate-600">Your interview is saved. This usually takes a short moment.</p>
        </section>
      )}

      {result?.status === 'failed' && (
        <section className="rounded-3xl border border-rose-200 bg-white p-8 shadow-sm">
          <h2 className="text-lg font-semibold text-rose-800">We couldn’t generate your report</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">Your interview is still saved. Please try loading the report again later.</p>
          <Link to="/dashboard" className="mt-5 inline-flex rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white">Back to dashboard</Link>
        </section>
      )}

      {result?.status === 'ready' && report && <>
        <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div><p className="text-sm font-semibold text-slate-500">Overall score</p><p className="mt-1 text-5xl font-semibold tracking-tight text-indigo-700">{report.overall_score}<span className="text-2xl text-slate-400">/100</span></p></div>
            <p className="max-w-xl text-sm leading-6 text-slate-700">{report.summary}</p>
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h2 className="text-lg font-semibold">Skill scores</h2>
          <div className="mt-6 space-y-5">{report.skill_scores.map((item) => <ScoreBar key={item.skill} label={item.skill} score={item.score} comment={item.comment} />)}</div>
        </section>

        <div className="grid gap-6 md:grid-cols-2">
          <section className="rounded-3xl border border-emerald-200 bg-emerald-50/50 p-7">
            <h2 className="text-lg font-semibold text-emerald-900">Strengths</h2>
            <ul className="mt-4 list-disc space-y-3 pl-5 text-sm leading-6 text-slate-700">{report.strengths.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
          </section>
          <section className="rounded-3xl border border-amber-200 bg-amber-50/50 p-7">
            <h2 className="text-lg font-semibold text-amber-950">Gaps to work on</h2>
            <ul className="mt-4 list-disc space-y-3 pl-5 text-sm leading-6 text-slate-700">{report.gaps.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
          </section>
        </div>

        <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h2 className="text-lg font-semibold">Question-by-question feedback</h2>
          <div className="mt-4 divide-y divide-slate-100">{report.question_feedback.map((item, index) => (
            <details key={`${index}-${item.question}`} className="group py-4">
              <summary className="cursor-pointer list-none font-medium text-slate-800 marker:hidden">{item.question}<span className="float-right text-indigo-600 group-open:rotate-45">＋</span></summary>
              <div className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
                <p><strong className="text-slate-800">Your answer:</strong> {item.answer_summary}</p>
                <p><strong className="text-slate-800">Feedback:</strong> {item.feedback}</p>
                <div><strong className="text-slate-800">A strong answer could include:</strong><ul className="mt-1 list-disc pl-5">{item.ideal_answer_points.map((point, pointIndex) => <li key={`${pointIndex}-${point}`}>{point}</li>)}</ul></div>
              </div>
            </details>
          ))}</div>
        </section>

        <div className="grid gap-6 md:grid-cols-2">
          <section className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm"><h2 className="text-lg font-semibold">Communication notes</h2><p className="mt-3 text-sm leading-6 text-slate-600">{report.communication_notes}</p></section>
          <section className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm"><h2 className="text-lg font-semibold">What to practice next</h2><ol className="mt-4 list-decimal space-y-3 pl-5 text-sm leading-6 text-slate-600">{report.next_steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol></section>
        </div>
      </>}

      <div className="flex flex-wrap gap-3 pb-4"><Link to="/dashboard" className="rounded-full bg-indigo-600 px-6 py-3 text-sm font-semibold text-white">Back to dashboard</Link><button type="button" onClick={() => { setError(''); setLoadFailed(false); setRefreshKey((key) => key + 1) }} className="rounded-full border border-slate-300 px-6 py-3 text-sm font-semibold text-slate-700">Refresh report</button></div>
    </div>
  )
}

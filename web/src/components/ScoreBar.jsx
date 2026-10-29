export default function ScoreBar({ label, score, comment }) {
  const value = Math.max(0, Math.min(100, Number(score) || 0))
  return (
    <div>
      <div className="flex items-center justify-between gap-4 text-sm">
        <span className="font-medium text-slate-800">{label}</span>
        <span className="font-semibold tabular-nums text-slate-700">{value}/100</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-label={`${label} score`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}>
        <div className="h-full rounded-full bg-indigo-600" style={{ width: `${value}%` }} />
      </div>
      {comment && <p className="mt-2 text-sm leading-6 text-slate-600">{comment}</p>}
    </div>
  )
}

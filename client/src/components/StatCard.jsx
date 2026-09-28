import { Skeleton } from './ui/States'

const TONES = {
  slate: 'bg-slate-100 text-slate-600',
  brand: 'bg-brand-50 text-brand-700',
  amber: 'bg-amber-50 text-amber-700',
  emerald: 'bg-emerald-50 text-emerald-700',
  rose: 'bg-rose-50 text-rose-700',
}

export function StatCard({ label, value, icon: Icon, tone = 'slate', loading, hint }) {
  return (
    <div className="card flex items-start justify-between gap-3 p-5">
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        {loading ? (
          <Skeleton className="mt-2 h-8 w-14" />
        ) : (
          <p className="mt-1 text-3xl font-semibold tracking-tight text-slate-900 tabular-nums">{value ?? '—'}</p>
        )}
        {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
      </div>
      {Icon && (
        <span className={`rounded-lg p-2 ${TONES[tone]}`} aria-hidden>
          <Icon className="size-5" />
        </span>
      )}
    </div>
  )
}

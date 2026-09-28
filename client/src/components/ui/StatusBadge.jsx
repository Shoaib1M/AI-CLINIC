import { capitalize } from '../../lib/format'

const STYLES = {
  pending: 'border-amber-200 bg-amber-50 text-amber-800',
  completed: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  cancelled: 'border-slate-200 bg-slate-100 text-slate-600',
}
const DOTS = { pending: 'bg-amber-500', completed: 'bg-emerald-500', cancelled: 'bg-slate-400' }

export function StatusBadge({ status }) {
  return (
    <span className={`chip ${STYLES[status] || STYLES.cancelled}`}>
      <span className={`size-1.5 rounded-full ${DOTS[status] || DOTS.cancelled}`} aria-hidden />
      {capitalize(status)}
    </span>
  )
}

import { AlertTriangle, Inbox, Loader2, RefreshCw } from 'lucide-react'

export function Spinner({ className = 'size-4' }) {
  return <Loader2 className={`animate-spin ${className}`} aria-hidden />
}

export function LoadingState({ label = 'Loading…' }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
      <Spinner /> {label}
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded-md bg-slate-200/70 ${className}`} aria-hidden />
}

export function EmptyState({ icon: Icon = Inbox, title, description, action }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-3 rounded-full bg-slate-100 p-3 text-slate-500">
        <Icon className="size-5" aria-hidden />
      </div>
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry, title = 'Something went wrong' }) {
  return (
    <div role="alert" className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-3 rounded-full bg-rose-50 p-3 text-rose-600">
        <AlertTriangle className="size-5" aria-hidden />
      </div>
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-slate-500">{error?.message || 'Please try again.'}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary mt-4" onClick={onRetry}>
          <RefreshCw className="size-4" aria-hidden /> Try again
        </button>
      )}
    </div>
  )
}

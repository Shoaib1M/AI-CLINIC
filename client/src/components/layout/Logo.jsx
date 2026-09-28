import { Link } from 'react-router'

export function Logo({ to = '/', className = '' }) {
  return (
    <Link to={to} className={`inline-flex items-center gap-2 font-semibold tracking-tight text-slate-900 ${className}`}>
      <span className="grid size-7 place-items-center rounded-lg bg-brand-700 text-white" aria-hidden>
        <svg viewBox="0 0 32 32" className="size-4"><path d="M13 8h6v5h5v6h-5v5h-6v-5H8v-6h5z" fill="currentColor" /></svg>
      </span>
      AI-CLINIC
    </Link>
  )
}

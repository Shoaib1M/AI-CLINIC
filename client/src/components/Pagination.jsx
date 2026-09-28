import { ChevronLeft, ChevronRight } from 'lucide-react'

export function Pagination({ meta, onPage }) {
  if (!meta || meta.pages <= 1) {
    return meta ? <p className="px-5 py-3 text-xs text-slate-500">{meta.total} result{meta.total === 1 ? '' : 's'}</p> : null
  }
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 border-t border-slate-100 px-5 py-3">
      <p className="text-xs text-slate-500">
        Page {meta.page} of {meta.pages} · {meta.total} results
      </p>
      <div className="flex gap-2">
        <button type="button" className="btn btn-secondary btn-sm" disabled={meta.page <= 1} onClick={() => onPage(meta.page - 1)}>
          <ChevronLeft className="size-3.5" aria-hidden /> Previous
        </button>
        <button type="button" className="btn btn-secondary btn-sm" disabled={meta.page >= meta.pages} onClick={() => onPage(meta.page + 1)}>
          Next <ChevronRight className="size-3.5" aria-hidden />
        </button>
      </div>
    </nav>
  )
}

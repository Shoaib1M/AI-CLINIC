import { useSearchParams } from 'react-router'
import { Ban, CheckCircle2, Clock, Search, Sparkles, Users } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useAppointments, useModelInfo, useStats } from '../hooks/queries'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useStatusChange } from '../hooks/useStatusChange'
import { PageHeader } from '../components/layout/AppShell'
import { StatCard } from '../components/StatCard'
import { AppointmentList } from '../components/AppointmentList'
import { Pagination } from '../components/Pagination'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States'
import { SORT_OPTIONS, STATUSES } from '../lib/constants'

const STATUS_TABS = [{ value: '', label: 'All' }, ...STATUSES]

export default function DoctorDashboard() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const status = params.get('status') || ''
  const disease = params.get('disease') || ''
  const sort = params.get('sort') || 'scheduled_at:desc'
  const page = Number(params.get('page') || 1)

  // The URL is the single source of truth for filters (shareable, back-button
  // friendly). Only the API request is debounced, not the input itself.
  const q = params.get('q') || ''
  const debouncedQ = useDebouncedValue(q, 300)

  // Build from the live URL rather than a render-time snapshot, so updates fired
  // from effects (the debounced search) never resurrect filters that were just cleared.
  const update = (changes) => {
    const next = new URLSearchParams(window.location.search)
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)))
    if (!('page' in changes)) next.delete('page')
    setParams(next, { replace: true })
  }

  const [sortField, order] = sort.split(':')
  const stats = useStats()
  const model = useModelInfo()
  const list = useAppointments({ q: debouncedQ, status, disease, sort: sortField, order, page, per_page: 15 })
  const statusChange = useStatusChange()
  const filtered = Boolean(q || status || disease)

  return (
    <>
      <PageHeader eyebrow="Doctor workspace" title={`Welcome, ${user.full_name}`} description="Review the queue, check AI suggestions and write prescriptions." />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total patients" value={stats.data?.total_patients} icon={Users} loading={stats.isLoading} />
        <StatCard label="Pending" value={stats.data?.by_status.pending} icon={Clock} tone="amber" loading={stats.isLoading} />
        <StatCard label="Completed" value={stats.data?.by_status.completed} icon={CheckCircle2} tone="emerald" loading={stats.isLoading} />
        <StatCard label="Cancelled" value={stats.data?.by_status.cancelled} icon={Ban} tone="rose" loading={stats.isLoading} />
      </div>

      {stats.data?.top_predicted_diseases.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="flex items-center gap-1.5 text-slate-500">
            <Sparkles className="size-3.5 text-ai-600" aria-hidden /> Most frequent AI suggestions:
          </span>
          {stats.data.top_predicted_diseases.map(({ disease: d, count }) => (
            <button
              key={d}
              type="button"
              onClick={() => update({ disease: disease === d ? '' : d })}
              aria-pressed={disease === d}
              className={`chip cursor-pointer ${disease === d ? 'border-ai-500 bg-ai-50 text-ai-700' : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'}`}
            >
              {d} <span className="text-slate-400">{count}</span>
            </button>
          ))}
        </div>
      )}

      <section className="card mt-6" aria-labelledby="queue-heading">
        <div className="space-y-3 border-b border-slate-100 px-5 py-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <h2 id="queue-heading" className="card-title">Patient queue</h2>
            <div role="tablist" aria-label="Filter by status" className="flex gap-1 overflow-x-auto rounded-lg bg-slate-100 p-1">
              {STATUS_TABS.map((tab) => (
                <button
                  key={tab.value}
                  type="button"
                  role="tab"
                  aria-selected={status === tab.value}
                  onClick={() => update({ status: tab.value })}
                  className={`rounded-md px-3 py-1 text-sm font-medium whitespace-nowrap ${
                    status === tab.value ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  {tab.label}
                  {tab.value && stats.data && <span className="ml-1.5 text-xs text-slate-400">{stats.data.by_status[tab.value]}</span>}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-[1fr_12rem_14rem]">
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
              <input
                type="search"
                aria-label="Search patients"
                placeholder="Search by name, phone, symptom or suggested condition…"
                className="input pl-9"
                value={q}
                onChange={(e) => update({ q: e.target.value })}
              />
            </div>
            <select aria-label="Filter by AI-suggested condition" className="input" value={disease} onChange={(e) => update({ disease: e.target.value })}>
              <option value="">All conditions</option>
              {(model.data?.classes || []).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select aria-label="Sort" className="input" value={sort} onChange={(e) => update({ sort: e.target.value })}>
              {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        </div>

        {list.isLoading ? (
          <LoadingState label="Loading patients…" />
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={list.refetch} />
        ) : list.data.data.length === 0 ? (
          <EmptyState
            title={filtered ? 'No patients match these filters' : 'The queue is empty'}
            description={filtered ? 'Clear the search or filters to see everyone.' : 'Appointments booked by the front desk will appear here.'}
            action={
              filtered && (
                <button type="button" className="btn btn-secondary" onClick={() => setParams({}, { replace: true })}>
                  Clear filters
                </button>
              )
            }
          />
        ) : (
          <div className={list.isPlaceholderData ? 'opacity-60 transition-opacity' : ''}>
            <AppointmentList appointments={list.data.data} role="doctor" onStatus={statusChange.request} busyId={statusChange.busyId} />
            <Pagination meta={list.data.meta} onPage={(p) => update({ page: String(p) })} />
          </div>
        )}
      </section>
      {statusChange.dialog}
    </>
  )
}

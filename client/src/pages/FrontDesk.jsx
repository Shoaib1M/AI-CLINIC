import { useState } from 'react'
import { Link } from 'react-router'
import { CalendarCheck, CalendarPlus, Clock, Search, Users } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useAppointments, useStats } from '../hooks/queries'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useStatusChange } from '../hooks/useStatusChange'
import { PageHeader } from '../components/layout/AppShell'
import { StatCard } from '../components/StatCard'
import { AppointmentList } from '../components/AppointmentList'
import { Pagination } from '../components/Pagination'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States'
import { STATUSES } from '../lib/constants'

export default function FrontDesk() {
  const { user } = useAuth()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const search = useDebouncedValue(q, 300)

  const stats = useStats()
  const list = useAppointments({ q: search, status, page, per_page: 10, sort: 'created_at', order: 'desc' })
  const statusChange = useStatusChange()

  const newButton = (
    <Link to="/frontdesk/new" className="btn btn-primary">
      <CalendarPlus className="size-4" aria-hidden /> New appointment
    </Link>
  )

  return (
    <>
      <PageHeader eyebrow="Front desk" title={`Hello, ${user.full_name.split(' ')[0]}`} description="Book visits, capture symptoms and keep the queue up to date." actions={newButton} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Scheduled today" value={stats.data?.scheduled_today} icon={CalendarCheck} tone="brand" loading={stats.isLoading} />
        <StatCard label="Pending" value={stats.data?.by_status.pending} icon={Clock} tone="amber" loading={stats.isLoading} />
        <StatCard label="Registered patients" value={stats.data?.total_patients} icon={Users} loading={stats.isLoading} />
      </div>

      <section className="card mt-6" aria-labelledby="recent-heading">
        <div className="card-header flex-col items-stretch sm:flex-row sm:items-center">
          <h2 id="recent-heading" className="card-title">Appointments</h2>
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
              <input
                type="search"
                aria-label="Search appointments"
                placeholder="Search name, phone, symptom…"
                className="input pl-9 sm:w-64"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value)
                  setPage(1)
                }}
              />
            </div>
            <select aria-label="Filter by status" className="input sm:w-40" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
              <option value="">All statuses</option>
              {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
        </div>

        {list.isLoading ? (
          <LoadingState label="Loading appointments…" />
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={list.refetch} />
        ) : list.data.data.length === 0 ? (
          search || status ? (
            <EmptyState title="No matching appointments" description="Try a different search or clear the status filter." />
          ) : (
            <EmptyState icon={CalendarPlus} title="No appointments yet" description="Book the first appointment to see it here." action={newButton} />
          )
        ) : (
          <div className={list.isPlaceholderData ? 'opacity-60 transition-opacity' : ''}>
            <AppointmentList appointments={list.data.data} role="frontdesk" onStatus={statusChange.request} busyId={statusChange.busyId} />
            <Pagination meta={list.data.meta} onPage={setPage} />
          </div>
        )}
      </section>
      {statusChange.dialog}
    </>
  )
}

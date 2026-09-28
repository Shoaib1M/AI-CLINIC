import { Link } from 'react-router'
import { Ban, CheckCircle2, FilePlus2, RotateCcw } from 'lucide-react'
import { appointmentTypeLabel, formatDate, formatTime, percent } from '../lib/format'
import { StatusBadge } from './ui/StatusBadge'

function SymptomSummary({ symptoms }) {
  const shown = symptoms.slice(0, 3)
  return (
    <div className="flex flex-wrap gap-1">
      {shown.map((s) => (
        <span key={s} className="chip border-slate-200 bg-slate-50 font-normal text-slate-600">{s}</span>
      ))}
      {symptoms.length > shown.length && <span className="chip border-transparent text-slate-400">+{symptoms.length - shown.length}</span>}
    </div>
  )
}

function Suggestion({ prediction }) {
  if (!prediction || prediction.status !== 'ok') return <span className="text-xs text-slate-400">No suggestion</span>
  return (
    <div>
      <p className="text-sm font-medium text-slate-800">{prediction.predicted_disease}</p>
      <p className="text-xs text-slate-500">{percent(prediction.confidence)} model confidence</p>
    </div>
  )
}

// `compact` renders Complete/Cancel as icon buttons (with accessible names) so the
// table row stays on one line; the mobile cards show full labels.
function Actions({ appointment, role, onStatus, busy, compact = false }) {
  const { status } = appointment
  const icon = 'size-3.5'
  const label = (text) => (compact ? <span className="sr-only">{text}</span> : text)
  const iconOnly = compact ? 'px-2' : ''
  return (
    <div className={`flex justify-end gap-1.5 ${compact ? '' : 'flex-wrap'}`}>
      {role === 'doctor' && status === 'pending' && (
        <button type="button" className={`btn btn-secondary btn-sm ${iconOnly}`} title="Mark completed" disabled={busy} onClick={() => onStatus(appointment, 'completed')}>
          <CheckCircle2 className={icon} aria-hidden /> {label('Complete')}
        </button>
      )}
      {role === 'doctor' && status !== 'cancelled' && (
        <Link to={`/appointments/${appointment.id}?prescribe=1`} className="btn btn-secondary btn-sm">
          <FilePlus2 className={icon} aria-hidden /> Prescribe
        </Link>
      )}
      {status === 'pending' && (
        <button type="button" className={`btn btn-danger btn-sm ${iconOnly}`} title="Cancel appointment" disabled={busy} onClick={() => onStatus(appointment, 'cancelled')}>
          <Ban className={icon} aria-hidden /> {label('Cancel')}
        </button>
      )}
      {role === 'frontdesk' && status === 'cancelled' && (
        <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => onStatus(appointment, 'pending')}>
          <RotateCcw className={icon} aria-hidden /> Reinstate
        </button>
      )}
    </div>
  )
}

export function AppointmentList({ appointments, role, onStatus, busyId }) {
  return (
    <>
      {/* Table on medium screens and up */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-100 text-xs text-slate-500">
            <tr>
              <th scope="col" className="px-5 py-2.5 font-medium">Patient</th>
              <th scope="col" className="px-3 py-2.5 font-medium">Scheduled</th>
              <th scope="col" className="hidden px-3 py-2.5 font-medium xl:table-cell">Symptoms</th>
              <th scope="col" className="px-3 py-2.5 font-medium">AI suggestion</th>
              <th scope="col" className="px-3 py-2.5 font-medium">Status</th>
              <th scope="col" className="px-5 py-2.5 text-right font-medium"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {appointments.map((a) => (
              <tr key={a.id} className="align-top hover:bg-slate-50/60">
                <td className="px-5 py-3">
                  <Link to={`/appointments/${a.id}`} className="font-medium whitespace-nowrap text-slate-900 hover:text-brand-700 hover:underline">
                    {a.patient.full_name}
                  </Link>
                  <p className="text-xs whitespace-nowrap text-slate-500">{a.patient.phone}</p>
                </td>
                <td className="px-3 py-3 whitespace-nowrap">
                  <p className="text-slate-800">{formatDate(a.scheduled_at)}</p>
                  <p className="text-xs text-slate-500">{formatTime(a.scheduled_at)} · {appointmentTypeLabel(a.appointment_type)}</p>
                </td>
                <td className="hidden max-w-60 px-3 py-3 xl:table-cell"><SymptomSummary symptoms={a.symptoms} /></td>
                <td className="px-3 py-3"><Suggestion prediction={a.prediction} /></td>
                <td className="px-3 py-3"><StatusBadge status={a.status} /></td>
                <td className="px-5 py-3">
                  <Actions appointment={a} role={role} onStatus={onStatus} busy={busyId === a.id} compact />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Cards on small screens */}
      <ul className="divide-y divide-slate-100 md:hidden">
        {appointments.map((a) => (
          <li key={a.id} className="space-y-3 px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <Link to={`/appointments/${a.id}`} className="font-medium text-slate-900 hover:underline">{a.patient.full_name}</Link>
                <p className="text-xs text-slate-500">
                  {formatDate(a.scheduled_at)}, {formatTime(a.scheduled_at)} · {appointmentTypeLabel(a.appointment_type)}
                </p>
              </div>
              <StatusBadge status={a.status} />
            </div>
            <SymptomSummary symptoms={a.symptoms} />
            <div className="flex flex-wrap items-end justify-between gap-3">
              <Suggestion prediction={a.prediction} />
              <Actions appointment={a} role={role} onStatus={onStatus} busy={busyId === a.id} />
            </div>
          </li>
        ))}
      </ul>
    </>
  )
}

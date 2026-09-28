import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { AlertTriangle, ArrowLeft, Ban, CalendarClock, CheckCircle2, Download, FilePlus2, FileText, History, RotateCcw } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useAppointment, useModelInfo, useUpdateAppointment } from '../hooks/queries'
import { useStatusChange } from '../hooks/useStatusChange'
import { api } from '../lib/api'
import { APPOINTMENT_TYPES } from '../lib/constants'
import { appointmentTypeLabel, formatDateTime, formatTimestamp, todayISO } from '../lib/format'
import { PredictionCard } from '../components/PredictionCard'
import { PrescriptionDialog } from '../components/PrescriptionDialog'
import { Modal } from '../components/ui/Modal'
import { Field } from '../components/ui/Field'
import { EmptyState, ErrorState, LoadingState, Spinner } from '../components/ui/States'
import { StatusBadge } from '../components/ui/StatusBadge'

function Section({ title, icon: Icon, children, actions }) {
  return (
    <section className="card" aria-label={title}>
      <div className="card-header">
        <h2 className="card-title flex items-center gap-2">
          {Icon && <Icon className="size-4 text-slate-400" aria-hidden />} {title}
        </h2>
        {actions}
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

function Detail({ label, children }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-slate-900">{children}</dd>
    </div>
  )
}

function RescheduleDialog({ open, onClose, appointment }) {
  const [date, time] = appointment.scheduled_at.split('T')
  const [form, setForm] = useState({ date, time, type: appointment.appointment_type })
  const [error, setError] = useState(null)
  const mutation = useUpdateAppointment()
  const toast = useToast()

  const submit = (event) => {
    event.preventDefault()
    if (!form.date || !form.time) return setError('Choose a date and time.')
    mutation.mutate(
      { id: appointment.id, changes: { scheduled_at: `${form.date}T${form.time}`, appointment_type: form.type } },
      {
        onSuccess: () => {
          toast.success('Appointment rescheduled.')
          onClose()
        },
        onError: (err) => setError(Object.values(err.details)[0] || err.message),
      },
    )
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title="Reschedule appointment"
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" form="reschedule-form" className="btn btn-primary" disabled={mutation.isPending}>
            {mutation.isPending && <Spinner />} Save
          </button>
        </>
      }
    >
      <form id="reschedule-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
        {error && <p role="alert" className="text-sm text-rose-600 sm:col-span-2">{error}</p>}
        <Field label="Date"><input type="date" min={todayISO()} value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></Field>
        <Field label="Time"><input type="time" step={900} value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} /></Field>
        <Field label="Type" className="sm:col-span-2">
          <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            {APPOINTMENT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </Field>
      </form>
    </Modal>
  )
}

export default function AppointmentDetails() {
  const { id } = useParams()
  const { user } = useAuth()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const { data: appointment, isLoading, isError, error, refetch } = useAppointment(id)
  const model = useModelInfo()
  const statusChange = useStatusChange()
  const [rescheduling, setRescheduling] = useState(false)
  const [downloading, setDownloading] = useState(null)

  const back = user.role === 'doctor' ? '/doctor' : '/frontdesk'
  const backLink = (
    <Link to={back} className="inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-900">
      <ArrowLeft className="size-4" aria-hidden /> Back to dashboard
    </Link>
  )

  if (isLoading) return <LoadingState label="Loading appointment…" />
  if (isError) {
    return (
      <>
        {backLink}
        <div className="card mt-4">
          <ErrorState title={error.status === 404 ? 'Appointment not found' : undefined} error={error} onRetry={error.status === 404 ? undefined : refetch} />
        </div>
      </>
    )
  }

  const isDoctor = user.role === 'doctor'
  const { status, patient, prediction } = appointment
  const prescribing = params.get('prescribe') === '1' && isDoctor && status !== 'cancelled'
  const setPrescribing = (open) => setParams(open ? { prescribe: '1' } : {}, { replace: true })
  const vocabulary = new Set(model.data?.symptoms || [])

  const download = async (rxId) => {
    setDownloading(rxId)
    try {
      await api.downloadPrescriptionPdf(rxId)
    } catch (err) {
      toast.error(`PDF download failed: ${err.message}`)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <>
      {backLink}
      <div className="mt-3 mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{patient.full_name}</h1>
            <StatusBadge status={status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Appointment A-{String(appointment.id).padStart(5, '0')} · {formatDateTime(appointment.scheduled_at)} · {appointmentTypeLabel(appointment.appointment_type)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2" aria-label="Actions">
          {isDoctor && status === 'pending' && (
            <button type="button" className="btn btn-secondary" onClick={() => statusChange.request(appointment, 'completed')}>
              <CheckCircle2 className="size-4" aria-hidden /> Mark completed
            </button>
          )}
          {!isDoctor && status === 'pending' && (
            <button type="button" className="btn btn-secondary" onClick={() => setRescheduling(true)}>
              <CalendarClock className="size-4" aria-hidden /> Reschedule
            </button>
          )}
          {status === 'pending' && (
            <button type="button" className="btn btn-danger" onClick={() => statusChange.request(appointment, 'cancelled')}>
              <Ban className="size-4" aria-hidden /> Cancel
            </button>
          )}
          {!isDoctor && status === 'cancelled' && (
            <button type="button" className="btn btn-secondary" onClick={() => statusChange.request(appointment, 'pending')}>
              <RotateCcw className="size-4" aria-hidden /> Reinstate
            </button>
          )}
          {isDoctor && status !== 'cancelled' && (
            <button type="button" className="btn btn-primary" onClick={() => setPrescribing(true)}>
              <FilePlus2 className="size-4" aria-hidden /> Write prescription
            </button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Section title="Patient information">
              <dl className="grid grid-cols-2 gap-4">
                <Detail label="Full name">{patient.full_name}</Detail>
                <Detail label="Patient ID">P-{String(patient.id).padStart(5, '0')}</Detail>
                <Detail label="Phone"><a href={`tel:${patient.phone.replace(/[^\d+]/g, '')}`} className="hover:underline">{patient.phone}</a></Detail>
                <Detail label="Registered">{formatTimestamp(patient.created_at)}</Detail>
              </dl>
            </Section>
            <Section title="Appointment information">
              <dl className="grid grid-cols-2 gap-4">
                <Detail label="Scheduled for">{formatDateTime(appointment.scheduled_at)}</Detail>
                <Detail label="Type">{appointmentTypeLabel(appointment.appointment_type)}</Detail>
                <Detail label="Booked by">{appointment.created_by?.full_name || '—'}</Detail>
                <Detail label="Last updated">{formatTimestamp(appointment.updated_at)}</Detail>
              </dl>
            </Section>
          </div>

          <Section title="Symptoms">
            <ul className="flex flex-wrap gap-2" aria-label="Recorded symptoms">
              {appointment.symptoms.map((s) => {
                const recognised = !model.data || vocabulary.has(s)
                return (
                  <li key={s} className={`chip px-2.5 py-1 text-sm ${recognised ? 'border-slate-200 bg-slate-50 text-slate-700' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>
                    {!recognised && <AlertTriangle className="size-3.5" aria-label="Not recognised by the model" />} {s}
                  </li>
                )
              })}
            </ul>
            <p className="hint">As reported at the front desk. Symptoms highlighted in amber were not used by the model.</p>
          </Section>

          <Section
            title="Prescriptions"
            icon={FileText}
            actions={isDoctor && status !== 'cancelled' && appointment.prescriptions.length > 0 && (
              <button type="button" className="btn btn-ghost btn-sm text-brand-700" onClick={() => setPrescribing(true)}>
                <FilePlus2 className="size-3.5" aria-hidden /> New
              </button>
            )}
          >
            {appointment.prescriptions.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="No prescription yet"
                description={isDoctor ? 'Prescriptions are written by the doctor. The AI suggestion is never turned into one automatically.' : 'The doctor has not written a prescription for this visit.'}
                action={isDoctor && status !== 'cancelled' && (
                  <button type="button" className="btn btn-primary" onClick={() => setPrescribing(true)}>
                    <FilePlus2 className="size-4" aria-hidden /> Write prescription
                  </button>
                )}
              />
            ) : (
              <ul className="space-y-4">
                {appointment.prescriptions.map((rx) => (
                  <li key={rx.id} className="rounded-lg border border-slate-200 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold">{rx.diagnosis}</p>
                        <p className="text-xs text-slate-500">RX-{String(rx.id).padStart(6, '0')} · {rx.doctor?.full_name} · {formatTimestamp(rx.created_at)}</p>
                      </div>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => download(rx.id)} disabled={downloading === rx.id}>
                        {downloading === rx.id ? <Spinner className="size-3.5" /> : <Download className="size-3.5" aria-hidden />} PDF
                      </button>
                    </div>
                    <ol className="mt-3 space-y-1.5 text-sm">
                      {rx.medications.map((m, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="text-slate-400 tabular-nums">{i + 1}.</span>
                          <span>
                            <span className="font-medium">{m.name}</span>
                            {m.dosage && <span className="text-slate-600"> · {m.dosage}</span>}
                            {m.instructions && <span className="block text-slate-500">{m.instructions}</span>}
                          </span>
                        </li>
                      ))}
                    </ol>
                    {rx.notes && <p className="mt-3 border-t border-slate-100 pt-3 text-sm text-slate-600">{rx.notes}</p>}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        <div className="space-y-6">
          <PredictionCard prediction={prediction} showTreatments />
          <Section title="Visit history" icon={History}>
            {appointment.visit_history.length === 0 ? (
              <p className="text-sm text-slate-500">This is the patient’s first recorded visit.</p>
            ) : (
              <ul className="space-y-3">
                {appointment.visit_history.map((v) => (
                  <li key={v.id} className="flex items-start justify-between gap-3 text-sm">
                    <Link to={`/appointments/${v.id}`} className="hover:underline">
                      <span className="block font-medium text-slate-800">{formatDateTime(v.scheduled_at)}</span>
                      <span className="block text-xs text-slate-500">{appointmentTypeLabel(v.appointment_type)}{v.predicted_disease && ` · AI: ${v.predicted_disease}`}</span>
                    </Link>
                    <StatusBadge status={v.status} />
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      </div>

      {isDoctor && <PrescriptionDialog open={prescribing} onClose={() => setPrescribing(false)} appointment={appointment} />}
      {rescheduling && <RescheduleDialog open onClose={() => setRescheduling(false)} appointment={appointment} />}
      {statusChange.dialog}
    </>
  )
}

import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { ArrowLeft, CalendarPlus, CheckCircle2, UserPlus, UserSearch, X } from 'lucide-react'
import { useCreateAppointment, useModelInfo, usePredictionPreview } from '../hooks/queries'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useToast } from '../context/ToastContext'
import { PageHeader } from '../components/layout/AppShell'
import { Field } from '../components/ui/Field'
import { SymptomInput } from '../components/SymptomInput'
import { PatientSearch } from '../components/PatientSearch'
import { PredictionCard } from '../components/PredictionCard'
import { Spinner } from '../components/ui/States'
import { StatusBadge } from '../components/ui/StatusBadge'
import { APPOINTMENT_TYPES } from '../lib/constants'
import { appointmentTypeLabel, formatDateTime, todayISO } from '../lib/format'

function defaultTime() {
  const next = new Date(Date.now() + 60 * 60 * 1000)
  return `${String(next.getHours()).padStart(2, '0')}:00`
}

const NO_SYMPTOMS = []
const NO_ALIASES = {}
const INITIAL = { name: '', phone: '', date: todayISO(), time: defaultTime(), type: '' }

// Server field names -> form field names, so API validation errors land on the right input.
const SERVER_FIELDS = {
  'patient.full_name': 'name',
  'patient.phone': 'phone',
  patient: 'patient',
  patient_id: 'patient',
  scheduled_at: 'date',
  appointment_type: 'type',
  symptoms: 'symptoms',
}

function validate(form, mode, patient, symptoms) {
  const errors = {}
  if (mode === 'existing') {
    if (!patient) errors.patient = 'Select a patient, or switch to “New patient”.'
  } else {
    if (form.name.trim().length < 2) errors.name = 'Enter the patient’s full name.'
    const digits = form.phone.replace(/\D/g, '')
    if (!/^\+?[0-9 ()-]+$/.test(form.phone.trim()) || digits.length < 7 || digits.length > 15) {
      errors.phone = 'Enter a valid phone number (7–15 digits).'
    }
  }
  if (!form.date) errors.date = 'Choose a date.'
  else if (form.date < todayISO()) errors.date = 'The date cannot be in the past.'
  if (!form.time) errors.time = 'Choose a time.'
  if (!form.type) errors.type = 'Choose an appointment type.'
  if (!symptoms.length) errors.symptoms = 'Add at least one symptom.'
  return errors
}

function BookingResult({ appointment, onReset }) {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="card flex flex-col gap-4 p-6 sm:flex-row sm:items-start">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-emerald-50 text-emerald-600">
          <CheckCircle2 className="size-5" aria-hidden />
        </span>
        <div className="flex-1">
          <h2 className="text-lg font-semibold">Appointment booked</h2>
          <p className="mt-1 text-sm text-slate-500">
            {appointment.patient.full_name} · {formatDateTime(appointment.scheduled_at)} · {appointmentTypeLabel(appointment.appointment_type)}
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
            <div><dt className="text-slate-500">Appointment</dt><dd className="font-medium">A-{String(appointment.id).padStart(5, '0')}</dd></div>
            <div><dt className="text-slate-500">Patient ID</dt><dd className="font-medium">P-{String(appointment.patient.id).padStart(5, '0')}</dd></div>
            <div><dt className="text-slate-500">Phone</dt><dd className="font-medium">{appointment.patient.phone}</dd></div>
            <div><dt className="text-slate-500">Status</dt><dd><StatusBadge status={appointment.status} /></dd></div>
          </dl>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link to={`/appointments/${appointment.id}`} className="btn btn-primary">View patient record</Link>
            <button type="button" className="btn btn-secondary" onClick={onReset}>
              <CalendarPlus className="size-4" aria-hidden /> Book another
            </button>
          </div>
        </div>
      </div>
      <PredictionCard prediction={appointment.prediction} title="AI suggestion recorded for the doctor" />
    </div>
  )
}

export default function NewAppointment() {
  const model = useModelInfo()
  const create = useCreateAppointment()
  const toast = useToast()

  const [mode, setMode] = useState('new')
  const [patient, setPatient] = useState(null)
  const [form, setForm] = useState(INITIAL)
  const [symptoms, setSymptoms] = useState([])
  const [errors, setErrors] = useState({})
  const [booked, setBooked] = useState(null)

  const vocabulary = model.data?.symptoms || NO_SYMPTOMS
  const aliases = model.data?.symptom_aliases || NO_ALIASES

  // Live preview only when at least one symptom is recognised (otherwise the API returns 422).
  const known = useMemo(() => symptoms.filter((s) => vocabulary.includes(s)), [symptoms, vocabulary])
  const debouncedKnown = useDebouncedValue(known, 400)
  const preview = usePredictionPreview(debouncedKnown)

  const set = (field) => (event) => {
    setForm((f) => ({ ...f, [field]: event.target.value }))
    setErrors((e) => ({ ...e, [field]: undefined }))
  }

  const reset = () => {
    setBooked(null)
    setPatient(null)
    setMode('new')
    setForm({ ...INITIAL, date: todayISO(), time: defaultTime() })
    setSymptoms([])
    setErrors({})
  }

  const submit = (event) => {
    event.preventDefault()
    const found = validate(form, mode, patient, symptoms)
    setErrors(found)
    if (Object.keys(found).length) return

    const payload = {
      scheduled_at: `${form.date}T${form.time}`,
      appointment_type: form.type,
      symptoms,
      ...(mode === 'existing'
        ? { patient_id: patient.id }
        : { patient: { full_name: form.name.trim(), phone: form.phone.trim() } }),
    }
    create.mutate(payload, {
      onSuccess: (appointment) => {
        setBooked(appointment)
        toast.success('Appointment booked.')
        window.scrollTo({ top: 0 })
      },
      onError: (error) => {
        const mapped = {}
        Object.entries(error.details || {}).forEach(([key, message]) => {
          mapped[SERVER_FIELDS[key] || 'form'] = message
        })
        setErrors({ form: error.message, ...mapped })
      },
    })
  }

  if (booked) {
    return (
      <>
        <PageHeader eyebrow="Front desk" title="New appointment" />
        <BookingResult appointment={booked} onReset={reset} />
      </>
    )
  }

  const modeButton = (value, label, Icon) => (
    <button
      type="button"
      role="radio"
      aria-checked={mode === value}
      onClick={() => {
        setMode(value)
        setErrors({})
      }}
      className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
        mode === value ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-700'
      }`}
    >
      <Icon className="size-4" aria-hidden /> {label}
    </button>
  )

  return (
    <>
      <PageHeader
        eyebrow="Front desk"
        title="New appointment"
        description="Register the visit and the presenting symptoms. The AI suggestion is saved for the doctor."
        actions={
          <Link to="/frontdesk" className="btn btn-secondary">
            <ArrowLeft className="size-4" aria-hidden /> Back to dashboard
          </Link>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <form onSubmit={submit} noValidate className="space-y-6">
          {errors.form && (
            <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{errors.form}</p>
          )}

          <section className="card" aria-labelledby="patient-heading">
            <div className="card-header">
              <h2 id="patient-heading" className="card-title">1. Patient</h2>
            </div>
            <div className="space-y-4 p-5">
              <div role="radiogroup" aria-label="Patient type" className="flex gap-1 rounded-lg bg-slate-100 p-1">
                {modeButton('new', 'New patient', UserPlus)}
                {modeButton('existing', 'Returning patient', UserSearch)}
              </div>

              {mode === 'new' ? (
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Full name" error={errors.name}>
                    <input value={form.name} onChange={set('name')} autoComplete="off" maxLength={100} />
                  </Field>
                  <Field label="Phone number" error={errors.phone} hint="Include the country code if outside India.">
                    <input type="tel" value={form.phone} onChange={set('phone')} autoComplete="off" maxLength={20} placeholder="+91 98765 43210" />
                  </Field>
                </div>
              ) : patient ? (
                <div className="flex items-center justify-between gap-3 rounded-lg border border-brand-200 bg-brand-50/60 p-3">
                  <div>
                    <p className="text-sm font-medium text-slate-900">{patient.full_name}</p>
                    <p className="text-xs text-slate-500">{patient.phone} · {patient.visit_count} previous visit(s)</p>
                  </div>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPatient(null)}>
                    <X className="size-3.5" aria-hidden /> Change
                  </button>
                </div>
              ) : (
                <PatientSearch
                  error={errors.patient}
                  onSelect={(p) => {
                    setPatient(p)
                    setErrors((e) => ({ ...e, patient: undefined }))
                  }}
                />
              )}
            </div>
          </section>

          <section className="card" aria-labelledby="visit-heading">
            <div className="card-header">
              <h2 id="visit-heading" className="card-title">2. Visit</h2>
            </div>
            <div className="grid gap-4 p-5 sm:grid-cols-3">
              <Field label="Date" error={errors.date}>
                <input type="date" min={todayISO()} value={form.date} onChange={set('date')} />
              </Field>
              <Field label="Time" error={errors.time}>
                <input type="time" step={900} value={form.time} onChange={set('time')} />
              </Field>
              <Field label="Visit type" error={errors.type}>
                <select value={form.type} onChange={set('type')}>
                  <option value="">Select…</option>
                  {APPOINTMENT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </Field>
            </div>
          </section>

          <section className="card" aria-labelledby="symptoms-heading">
            <div className="card-header">
              <h2 id="symptoms-heading" className="card-title">3. Presenting symptoms</h2>
              {model.isError && <span className="text-xs text-amber-700">Suggestions unavailable</span>}
            </div>
            <div className="p-5">
              <SymptomInput
                value={symptoms}
                onChange={(next) => {
                  setSymptoms(next)
                  setErrors((e) => ({ ...e, symptoms: undefined }))
                }}
                vocabulary={vocabulary}
                aliases={aliases}
                error={errors.symptoms}
              />
            </div>
          </section>

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Link to="/frontdesk" className="btn btn-secondary">Cancel</Link>
            <button type="submit" className="btn btn-primary" disabled={create.isPending}>
              {create.isPending ? <Spinner /> : <CalendarPlus className="size-4" aria-hidden />} Book appointment
            </button>
          </div>
        </form>

        <aside className="space-y-4 lg:sticky lg:top-8 lg:self-start" aria-label="AI preview">
          {known.length === 0 ? (
            <div className="card p-5 text-sm text-slate-500">
              <p className="font-medium text-slate-700">AI preview</p>
              <p className="mt-1">Add symptoms to see the model’s ranked suggestion. It is saved with the appointment for the doctor to review.</p>
            </div>
          ) : preview.isError ? (
            <div className="card p-5 text-sm text-slate-500">
              <p className="font-medium text-slate-700">AI preview unavailable</p>
              <p className="mt-1">{preview.error.message} You can still book the appointment.</p>
            </div>
          ) : preview.data ? (
            <div className={preview.isFetching ? 'opacity-60 transition-opacity' : ''}>
              <PredictionCard prediction={preview.data} title="AI preview" compact />
            </div>
          ) : (
            <div className="card flex items-center gap-2 p-5 text-sm text-slate-500"><Spinner /> Asking the model…</div>
          )}
          <p className="px-1 text-xs text-slate-500">
            Suggestions come from a model trained on synthetic data. They support, and never replace, the doctor’s judgement.
          </p>
        </aside>
      </div>
    </>
  )
}

import { useState } from 'react'
import { Plus, Sparkles, Trash2 } from 'lucide-react'
import { useCreatePrescription } from '../hooks/queries'
import { useToast } from '../context/ToastContext'
import { api } from '../lib/api'
import { Modal } from './ui/Modal'
import { Spinner } from './ui/States'

let nextKey = 1
const emptyMedication = () => ({ key: nextKey++, name: '', dosage: '', instructions: '' })

function validate({ diagnosis, medications }) {
  const errors = {}
  if (diagnosis.trim().length < 2) errors.diagnosis = 'Enter a diagnosis (at least 2 characters).'
  const filled = medications.filter((m) => m.name.trim() || m.dosage.trim() || m.instructions.trim())
  if (!filled.length) errors.medications = 'Add at least one medication or instruction.'
  filled.forEach((m) => {
    if (!m.name.trim()) errors[`med-${m.key}`] = 'Name is required.'
  })
  return errors
}

/**
 * Doctor-authored prescription. The form starts empty: the AI suggestion and
 * the dataset's recorded treatments are offered as hints the doctor can
 * explicitly insert, never pre-filled.
 */
export function PrescriptionDialog({ open, onClose, appointment }) {
  const [diagnosis, setDiagnosis] = useState('')
  const [medications, setMedications] = useState([emptyMedication()])
  const [notes, setNotes] = useState('')
  const [errors, setErrors] = useState({})
  const mutation = useCreatePrescription()
  const toast = useToast()

  const prediction = appointment.prediction?.status === 'ok' ? appointment.prediction : null
  const references = prediction?.reference_treatments || []

  const reset = () => {
    setDiagnosis('')
    setMedications([emptyMedication()])
    setNotes('')
    setErrors({})
  }
  const close = () => {
    if (mutation.isPending) return
    reset()
    onClose()
  }

  const updateMedication = (key, field, value) =>
    setMedications((all) => all.map((m) => (m.key === key ? { ...m, [field]: value } : m)))

  const addReference = (name) =>
    setMedications((all) => {
      const blank = all.find((m) => !m.name && !m.dosage && !m.instructions)
      return blank ? all.map((m) => (m === blank ? { ...m, name } : m)) : [...all, { ...emptyMedication(), name }]
    })

  const submit = (event) => {
    event.preventDefault()
    const found = validate({ diagnosis, medications })
    setErrors(found)
    if (Object.keys(found).length) return

    const payload = {
      appointment_id: appointment.id,
      diagnosis: diagnosis.trim(),
      notes: notes.trim() || null,
      medications: medications
        .filter((m) => m.name.trim())
        .map(({ name, dosage, instructions }) => ({ name, dosage: dosage || null, instructions: instructions || null })),
    }
    mutation.mutate(payload, {
      onSuccess: async (prescription) => {
        toast.success('Prescription saved. Downloading PDF…')
        reset()
        onClose()
        try {
          await api.downloadPrescriptionPdf(prescription.id)
        } catch (error) {
          toast.error(`PDF download failed: ${error.message}`)
        }
      },
      onError: (error) => {
        setErrors({ form: error.message })
      },
    })
  }

  return (
    <Modal
      open={open}
      onClose={close}
      size="lg"
      title="Write prescription"
      description={`For ${appointment.patient.full_name}. You are the prescriber; AI output is reference only.`}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={close} disabled={mutation.isPending}>Cancel</button>
          <button type="submit" form="prescription-form" className="btn btn-primary" disabled={mutation.isPending}>
            {mutation.isPending && <Spinner />} Save &amp; download PDF
          </button>
        </>
      }
    >
      <form id="prescription-form" onSubmit={submit} noValidate className="space-y-5">
        {errors.form && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{errors.form}</p>}

        {prediction && (
          <div className="rounded-lg border border-ai-200 bg-ai-50/60 p-3 text-sm">
            <p className="flex items-center gap-1.5 font-medium text-ai-700">
              <Sparkles className="size-3.5" aria-hidden /> AI suggestion at intake
            </p>
            <p className="mt-1 text-slate-600">
              {prediction.predicted_disease} ({Math.round(prediction.confidence * 100)}% model confidence).
              Verify clinically before using.
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setDiagnosis(`${prediction.predicted_disease} (suspected)`)}>
                Use as diagnosis draft
              </button>
              {references.map((name) => (
                <button key={name} type="button" className="btn btn-secondary btn-sm" onClick={() => addReference(name)}>
                  <Plus className="size-3" aria-hidden /> {name}
                </button>
              ))}
            </div>
            {references.length > 0 && <p className="hint">Buttons insert treatments recorded in the synthetic training data.</p>}
          </div>
        )}

        <div>
          <label htmlFor="rx-diagnosis" className="label">Diagnosis</label>
          <input
            id="rx-diagnosis"
            className={`input ${errors.diagnosis ? 'input-error' : ''}`}
            value={diagnosis}
            onChange={(e) => setDiagnosis(e.target.value)}
            maxLength={200}
            aria-invalid={errors.diagnosis ? true : undefined}
            aria-describedby={errors.diagnosis ? 'rx-diagnosis-error' : undefined}
          />
          {errors.diagnosis && <p id="rx-diagnosis-error" className="field-error">{errors.diagnosis}</p>}
        </div>

        <fieldset>
          <legend className="label">Medications &amp; instructions</legend>
          <div className="space-y-3">
            {medications.map((m, index) => (
              <div key={m.key} className="grid gap-2 rounded-lg border border-slate-200 p-3 sm:grid-cols-[1.3fr_1fr_auto]">
                <div>
                  <input
                    aria-label={`Medication ${index + 1} name`}
                    placeholder="Medication, e.g. Paracetamol 500 mg"
                    className={`input ${errors[`med-${m.key}`] ? 'input-error' : ''}`}
                    value={m.name}
                    maxLength={100}
                    onChange={(e) => updateMedication(m.key, 'name', e.target.value)}
                  />
                  {errors[`med-${m.key}`] && <p className="field-error">{errors[`med-${m.key}`]}</p>}
                </div>
                <input
                  aria-label={`Medication ${index + 1} dosage`}
                  placeholder="Dosage, e.g. 1 tablet"
                  className="input"
                  value={m.dosage}
                  maxLength={100}
                  onChange={(e) => updateMedication(m.key, 'dosage', e.target.value)}
                />
                <button
                  type="button"
                  className="btn btn-ghost self-start p-2 text-slate-400 hover:text-rose-600"
                  onClick={() => setMedications((all) => (all.length > 1 ? all.filter((x) => x.key !== m.key) : [emptyMedication()]))}
                  aria-label={`Remove medication ${index + 1}`}
                >
                  <Trash2 className="size-4" />
                </button>
                <input
                  aria-label={`Medication ${index + 1} instructions`}
                  placeholder="Instructions, e.g. every 6 hours after food for 3 days"
                  className="input sm:col-span-3"
                  value={m.instructions}
                  maxLength={300}
                  onChange={(e) => updateMedication(m.key, 'instructions', e.target.value)}
                />
              </div>
            ))}
          </div>
          {errors.medications && <p className="field-error">{errors.medications}</p>}
          <button
            type="button"
            className="btn btn-ghost btn-sm mt-2 text-brand-700"
            onClick={() => setMedications((all) => [...all, emptyMedication()])}
            disabled={medications.length >= 20}
          >
            <Plus className="size-3.5" aria-hidden /> Add medication
          </button>
        </fieldset>

        <div>
          <label htmlFor="rx-notes" className="label">
            Notes <span className="font-normal text-slate-400">(optional)</span>
          </label>
          <textarea id="rx-notes" rows={3} className="input" value={notes} maxLength={2000} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </form>
    </Modal>
  )
}

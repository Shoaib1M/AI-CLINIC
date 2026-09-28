import { useState } from 'react'
import { ConfirmDialog } from '../components/ui/Modal'
import { useToast } from '../context/ToastContext'
import { useUpdateAppointment } from './queries'

const COPY = {
  completed: {
    title: 'Mark appointment as completed?',
    body: (name) => `${name}'s visit will be marked as completed. Completed appointments cannot be changed afterwards.`,
    confirm: 'Mark completed',
    tone: 'primary',
    done: 'Appointment marked as completed.',
  },
  cancelled: {
    title: 'Cancel this appointment?',
    body: (name) => `${name}'s appointment will be cancelled. It can be reinstated later if needed.`,
    confirm: 'Cancel appointment',
    tone: 'danger',
    done: 'Appointment cancelled.',
  },
  pending: {
    title: 'Reinstate this appointment?',
    body: (name) => `${name}'s appointment will return to the pending queue.`,
    confirm: 'Reinstate',
    tone: 'primary',
    done: 'Appointment reinstated.',
  },
}

/** Confirmation dialog + mutation for appointment status changes. */
export function useStatusChange() {
  const [pending, setPending] = useState(null) // { appointment, status }
  const mutation = useUpdateAppointment()
  const toast = useToast()

  const request = (appointment, status) => setPending({ appointment, status })
  const close = () => !mutation.isPending && setPending(null)

  const confirm = () =>
    mutation.mutate(
      { id: pending.appointment.id, changes: { status: pending.status } },
      {
        onSuccess: () => toast.success(COPY[pending.status].done),
        onError: (error) => toast.error(error.message),
        onSettled: () => setPending(null),
      },
    )

  const copy = pending && COPY[pending.status]
  const dialog = (
    <ConfirmDialog
      open={Boolean(pending)}
      onClose={close}
      onConfirm={confirm}
      busy={mutation.isPending}
      title={copy?.title}
      description={copy?.body(pending.appointment.patient.full_name)}
      confirmLabel={copy?.confirm}
      tone={copy?.tone}
    />
  )
  return { request, dialog, busyId: mutation.isPending ? pending?.appointment.id : null }
}

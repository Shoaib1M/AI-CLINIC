import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import NewAppointment from '../pages/NewAppointment'
import { FRONTDESK, MODEL, Route, json, mockApi, renderApp, signIn } from './utils'

const PREDICTION = {
  prediction: 'Malaria',
  confidence: 0.92,
  confidence_level: 'high',
  top_predictions: [{ disease: 'Malaria', probability: 0.92 }, { disease: 'Influenza', probability: 0.05 }],
  warnings: [],
  model_version: 'rf-test',
}

beforeEach(() => signIn(FRONTDESK))
afterEach(() => vi.unstubAllGlobals())

const page = <Route path="/frontdesk/new" element={<NewAppointment />} />

async function fillForm(user) {
  await user.type(screen.getByLabelText('Full name'), 'Riya Kapoor')
  await user.type(screen.getByLabelText('Phone number'), '+91 99887 76655')
  await user.selectOptions(screen.getByLabelText('Visit type'), 'consultation')
  const symptoms = screen.getByRole('combobox', { name: 'Symptoms' })
  for (const s of ['fever', 'chills', 'vomit']) await user.type(symptoms, `${s}{Enter}`)
}

describe('New appointment flow', () => {
  it('validates on the client before calling the API', async () => {
    const fetchMock = mockApi({ 'GET /model': () => json({ data: MODEL }) })
    renderApp(page, { path: '/frontdesk/new' })
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /Book appointment/ }))
    expect(screen.getByText('Enter the patient’s full name.')).toBeInTheDocument()
    expect(screen.getByText('Enter a valid phone number (7–15 digits).')).toBeInTheDocument()
    expect(screen.getByText('Choose an appointment type.')).toBeInTheDocument()
    expect(screen.getByText('Add at least one symptom.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, o]) => o?.method === 'POST')).toBe(false)
  })

  it('previews the AI suggestion, books, and shows the patient record', async () => {
    let posted
    mockApi({
      'GET /model': () => json({ data: MODEL }),
      'POST /predictions': () => json({ data: PREDICTION }),
      'POST /appointments': ({ body }) => {
        posted = body
        return json(
          {
            data: {
              id: 13,
              patient: { id: 21, full_name: 'Riya Kapoor', phone: '+91 99887 76655' },
              scheduled_at: body.scheduled_at,
              appointment_type: body.appointment_type,
              status: 'pending',
              symptoms: body.symptoms,
              prediction: { status: 'ok', predicted_disease: 'Malaria', confidence: 0.92, confidence_level: 'high', top_predictions: PREDICTION.top_predictions, warnings: [] },
            },
          },
          201,
        )
      },
    })
    renderApp(page, { path: '/frontdesk/new' })
    const user = userEvent.setup()
    await screen.findByText(/Add symptoms to see/)
    await fillForm(user)

    const preview = await screen.findByRole('region', { name: 'AI preview' })
    expect(await within(preview).findByText('Malaria', { selector: 'p' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Book appointment/ }))
    expect(await screen.findByRole('heading', { name: 'Appointment booked' })).toBeInTheDocument()
    expect(posted).toMatchObject({
      patient: { full_name: 'Riya Kapoor', phone: '+91 99887 76655' },
      appointment_type: 'consultation',
      symptoms: ['fever', 'chills', 'vomiting'], // alias resolved via /api/model
    })
    expect(posted.scheduled_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
    expect(screen.getByRole('link', { name: 'View patient record' })).toHaveAttribute('href', '/appointments/13')
  })

  it('shows server validation errors next to the right field', async () => {
    mockApi({
      'GET /model': () => json({ data: MODEL }),
      'POST /predictions': () => json({ data: PREDICTION }),
      'POST /appointments': () =>
        json({ error: { code: 'INVALID_INPUT', message: 'The request contains invalid data.', details: { 'patient.phone': 'Phone already flagged by server.' } } }, 400),
    })
    renderApp(page, { path: '/frontdesk/new' })
    const user = userEvent.setup()
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: /Book appointment/ }))

    expect(await screen.findByText('Phone already flagged by server.')).toBeInTheDocument()
    expect(screen.getByLabelText('Phone number')).toHaveAttribute('aria-invalid', 'true')
  })
})

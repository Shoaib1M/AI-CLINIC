// Thin fetch wrapper around the Flask REST API.
//
// - Adds the JWT bearer token.
// - Unwraps the {"data": ..., "meta": ...} envelope.
// - Turns {"error": {code, message, details}} into an ApiError.
// - Notifies the auth layer on 401 so an expired session logs out cleanly.

const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

let tokenGetter = () => null
let unauthorizedHandler = () => {}

export function configureApi({ getToken, onUnauthorized }) {
  tokenGetter = getToken
  unauthorizedHandler = onUnauthorized
}

export class ApiError extends Error {
  constructor(status, { code = 'UNKNOWN_ERROR', message = 'Something went wrong.', details } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details || {}
  }
}

async function request(path, { method = 'GET', body, params, raw = false, auth = true } = {}) {
  const url = new URL(`${BASE_URL}/api${path}`, window.location.origin)
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value)
  })

  const headers = { Accept: raw ? 'application/pdf' : 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = auth ? tokenGetter() : null
  if (token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    response = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw new ApiError(0, { code: 'NETWORK_ERROR', message: 'Cannot reach the server. Is the API running?' })
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const error = new ApiError(response.status, payload.error)
    if (response.status === 401 && token) unauthorizedHandler(error)
    throw error
  }

  if (raw) return response
  const payload = await response.json()
  return payload.meta ? { data: payload.data, meta: payload.meta } : payload.data
}

export const api = {
  login: (username, password) => request('/auth/login', { method: 'POST', body: { username, password }, auth: false }),
  me: () => request('/auth/me'),

  health: () => request('/health', { auth: false }),
  modelInfo: () => request('/model', { auth: false }),
  predict: (symptoms, topK = 3) => request('/predictions', { method: 'POST', body: { symptoms, top_k: topK } }),

  listAppointments: (params) => request('/appointments', { params }),
  appointmentStats: () => request('/appointments/stats'),
  getAppointment: (id) => request(`/appointments/${id}`),
  createAppointment: (payload) => request('/appointments', { method: 'POST', body: payload }),
  updateAppointment: (id, changes) => request(`/appointments/${id}`, { method: 'PATCH', body: changes }),

  searchPatients: (q) => request('/patients', { params: { q } }),

  createPrescription: (payload) => request('/prescriptions', { method: 'POST', body: payload }),
  async downloadPrescriptionPdf(id) {
    const response = await request(`/prescriptions/${id}/pdf`, { raw: true })
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `prescription_RX-${String(id).padStart(6, '0')}.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  },
}

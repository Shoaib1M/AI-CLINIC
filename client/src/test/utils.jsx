import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi } from 'vitest'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'

export const DOCTOR = { id: 1, username: 'doctor1', full_name: 'Dr. Evelyn Reed', role: 'doctor' }
export const FRONTDESK = { id: 2, username: 'frontdesk1', full_name: 'Sarah Johnson', role: 'frontdesk' }

export function signIn(user) {
  const expires = new Date(Date.now() + 3600_000).toISOString()
  localStorage.setItem('ai-clinic.session', JSON.stringify({ token: 'test-token', expires_at: expires, user }))
}

export const json = (body, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))

/** Route fetch calls by "METHOD /path" to handler functions. */
export function mockApi(routes) {
  const fetchMock = vi.fn((url, options = {}) => {
    const { pathname } = new URL(url)
    const key = `${options.method || 'GET'} ${pathname.replace(/^\/api/, '')}`
    const handler = routes[key]
    if (!handler) return json({ error: { code: 'NOT_FOUND', message: `No mock for ${key}` } }, 404)
    return handler({ url: new URL(url), body: options.body ? JSON.parse(options.body) : undefined, headers: options.headers })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function renderApp(routes, { path = '/' } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <ToastProvider>
          <AuthProvider>
            <Routes>{routes}</Routes>
          </AuthProvider>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

export const MODEL = {
  loaded: true,
  model_version: 'rf-test',
  classes: ['Common Cold', 'Influenza', 'Malaria'],
  symptoms: ['chills', 'cough', 'fever', 'nausea', 'runny nose', 'vomiting'],
  symptom_aliases: { vomit: 'vomiting' },
}

export { Route }

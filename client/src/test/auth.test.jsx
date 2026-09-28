import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ProtectedRoute } from '../components/layout/ProtectedRoute'
import Login from '../pages/Login'
import { DOCTOR, FRONTDESK, Route, json, mockApi, renderApp, signIn } from './utils'

afterEach(() => vi.unstubAllGlobals())

const routes = (
  <>
    <Route path="/login" element={<Login />} />
    <Route element={<ProtectedRoute roles={['doctor']} />}>
      <Route path="/doctor" element={<h1>Doctor home</h1>} />
    </Route>
    <Route element={<ProtectedRoute roles={['frontdesk']} />}>
      <Route path="/frontdesk" element={<h1>Front desk home</h1>} />
    </Route>
  </>
)

describe('authentication', () => {
  it('redirects signed-out users to the login page', () => {
    renderApp(routes, { path: '/doctor' })
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('signs in and opens the workspace for the user role', async () => {
    const fetchMock = mockApi({
      'POST /auth/login': ({ body }) =>
        body.password === 'correct-horse'
          ? json({ data: { token: 't', expires_at: new Date(Date.now() + 3600_000).toISOString(), user: FRONTDESK } })
          : json({ error: { code: 'INVALID_CREDENTIALS', message: 'Invalid username or password.' } }, 401),
    })
    renderApp(routes, { path: '/login' })
    const user = userEvent.setup()

    await user.type(screen.getByLabelText('Username'), 'frontdesk1')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password.')

    await user.clear(screen.getByLabelText('Password'))
    await user.type(screen.getByLabelText('Password'), 'correct-horse')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'Front desk home' })).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('ai-clinic.session')).user.role).toBe('frontdesk')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('never ships demo credentials in the login page', () => {
    renderApp(routes, { path: '/login' })
    expect(document.body.textContent).not.toMatch(/password\s*[:|]\s*\w+/i)
  })

  it('sends users with the wrong role to their own workspace', () => {
    signIn(DOCTOR)
    renderApp(routes, { path: '/frontdesk' })
    expect(screen.getByRole('heading', { name: 'Doctor home' })).toBeInTheDocument()
  })

  it('ignores an expired stored session', async () => {
    localStorage.setItem(
      'ai-clinic.session',
      JSON.stringify({ token: 'old', expires_at: new Date(Date.now() - 1000).toISOString(), user: DOCTOR }),
    )
    renderApp(routes, { path: '/doctor' })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument())
    expect(localStorage.getItem('ai-clinic.session')).toBeNull()
  })
})

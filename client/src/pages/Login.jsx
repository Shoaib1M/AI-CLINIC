import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { ShieldCheck } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { HOME_ROUTE } from '../lib/constants'
import { Logo } from '../components/layout/Logo'
import { Spinner } from '../components/ui/States'

export default function Login() {
  const { login, isAuthenticated, user, notice } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  if (isAuthenticated) return <Navigate to={HOME_ROUTE[user.role]} replace />

  const submit = async (event) => {
    event.preventDefault()
    if (!form.username.trim() || !form.password) {
      setError('Enter your username and password.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const signedIn = await login(form.username.trim(), form.password)
      const from = location.state?.from
      navigate(from && from !== '/login' ? from : HOME_ROUTE[signedIn.role], { replace: true })
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Logo />
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
          <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
          <p className="mt-1 text-sm text-slate-500">Staff access for front desk and doctors. Your role decides which workspace opens.</p>

          {notice && !error && (
            <p role="status" className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{notice}</p>
          )}
          {error && (
            <p role="alert" className="mt-6 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</p>
          )}

          <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
            <div>
              <label htmlFor="username" className="label">Username</label>
              <input
                id="username"
                className="input"
                autoComplete="username"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                autoFocus
              />
            </div>
            <div>
              <label htmlFor="password" className="label">Password</label>
              <input
                id="password"
                type="password"
                className="input"
                autoComplete="current-password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>
            <button type="submit" className="btn btn-primary w-full py-2.5" disabled={submitting}>
              {submitting && <Spinner />} Sign in
            </button>
          </form>

          <p className="mt-6 text-xs text-slate-500">
            Running locally? Accounts are created with <code className="rounded bg-slate-100 px-1 py-0.5">flask seed-demo</code> using the
            passwords you set in <code className="rounded bg-slate-100 px-1 py-0.5">.env</code>. See the README.
          </p>
          <Link to="/" className="mt-8 text-sm font-medium text-brand-700 hover:underline">← Back to overview</Link>
        </div>
      </div>

      <div className="hidden flex-col justify-end bg-brand-900 p-12 text-brand-50 lg:flex">
        <ShieldCheck className="mb-6 size-8 text-brand-200" aria-hidden />
        <p className="max-w-md text-2xl leading-snug font-medium text-white">
          Front desk captures symptoms. The model offers a ranked, clearly-labelled suggestion. The doctor decides.
        </p>
        <p className="mt-4 max-w-md text-sm text-brand-200">
          Educational software trained on synthetic data. Not for real patient care.
        </p>
      </div>
    </div>
  )
}

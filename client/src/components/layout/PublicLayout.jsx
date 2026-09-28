import { Link, Outlet } from 'react-router'
import { useAuth } from '../../context/AuthContext'
import { HOME_ROUTE, REPO_URL } from '../../lib/constants'
import { Logo } from './Logo'

export function PublicLayout() {
  const { user } = useAuth()
  return (
    <div className="flex min-h-dvh flex-col bg-white">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <Logo />
          <nav aria-label="Primary" className="flex items-center gap-1 sm:gap-2">
            <Link to="/#how-it-works" className="btn btn-ghost hidden sm:inline-flex">How it works</Link>
            <Link to="/model" className="btn btn-ghost hidden sm:inline-flex">Model card</Link>
            {user ? (
              <Link to={HOME_ROUTE[user.role]} className="btn btn-primary">Open dashboard</Link>
            ) : (
              <Link to="/login" className="btn btn-primary">Sign in</Link>
            )}
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>
            AI-CLINIC is an educational portfolio project. It is not a medical device and must not be used for real patient care.
          </p>
          <a href={REPO_URL} className="shrink-0 font-medium text-slate-700 hover:text-slate-900" target="_blank" rel="noreferrer">
            Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}

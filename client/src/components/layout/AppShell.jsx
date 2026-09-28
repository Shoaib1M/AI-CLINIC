import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { BarChart3, CalendarPlus, LayoutDashboard, LogOut, Menu, X } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { initials } from '../../lib/format'
import { Logo } from './Logo'

const NAV = {
  frontdesk: [
    { to: '/frontdesk', label: 'Dashboard', icon: LayoutDashboard, end: true },
    { to: '/frontdesk/new', label: 'New appointment', icon: CalendarPlus },
  ],
  doctor: [{ to: '/doctor', label: 'Dashboard', icon: LayoutDashboard, end: true }],
}
const ROLE_LABEL = { doctor: 'Doctor', frontdesk: 'Front desk' }

function NavItems({ role }) {
  const items = [...NAV[role], { to: '/model', label: 'Model card', icon: BarChart3 }]
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              isActive ? 'bg-brand-50 text-brand-800' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`
          }
        >
          <Icon className="size-4" aria-hidden /> {label}
        </NavLink>
      ))}
    </nav>
  )
}

function UserFooter({ user, onLogout }) {
  return (
    <div className="flex items-center gap-3 border-t border-slate-200 pt-4">
      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-slate-100 text-xs font-semibold text-slate-700" aria-hidden>
        {initials(user.full_name)}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-900">{user.full_name}</p>
        <p className="text-xs text-slate-500">{ROLE_LABEL[user.role]}</p>
      </div>
      <button type="button" onClick={() => onLogout()} className="btn btn-ghost p-2" aria-label="Sign out" title="Sign out">
        <LogOut className="size-4" />
      </button>
    </div>
  )
}

export function AppShell() {
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const home = user.role === 'doctor' ? '/doctor' : '/frontdesk'

  useEffect(() => setMenuOpen(false), [location.pathname])

  return (
    <div className="min-h-dvh lg:pl-64">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-slate-200 bg-white px-4 py-5 lg:flex">
        <Logo to={home} className="px-2" />
        <div className="mt-8 flex-1">
          <NavItems role={user.role} />
        </div>
        <UserFooter user={user} onLogout={logout} />
      </aside>

      {/* Mobile top bar + drawer */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <Logo to={home} />
        <button
          type="button"
          className="btn btn-ghost p-2"
          onClick={() => setMenuOpen((v) => !v)}
          aria-expanded={menuOpen}
          aria-controls="mobile-nav"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
        >
          {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </header>
      {menuOpen && (
        <div id="mobile-nav" className="fixed inset-x-0 top-[57px] z-20 border-b border-slate-200 bg-white px-4 pt-3 pb-4 shadow-lg lg:hidden">
          <NavItems role={user.role} />
          <div className="mt-4">
            <UserFooter user={user} onLogout={logout} />
          </div>
        </div>
      )}

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <Outlet />
      </main>
    </div>
  )
}

export function PageHeader({ title, description, actions, eyebrow }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

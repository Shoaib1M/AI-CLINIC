import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '../../context/AuthContext'
import { HOME_ROUTE } from '../../lib/constants'

// UX guard only: it keeps signed-out users away from app screens. The real
// access control is enforced by the API on every request.
export function ProtectedRoute({ roles }) {
  const { user, isAuthenticated } = useAuth()
  const location = useLocation()

  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(user.role)) return <Navigate to={HOME_ROUTE[user.role]} replace />
  return <Outlet />
}

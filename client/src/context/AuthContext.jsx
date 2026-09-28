import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, configureApi } from '../lib/api'

// The session (JWT + user profile) is kept in localStorage so a page refresh
// keeps you signed in. Trade-off: a token in localStorage is readable by
// injected scripts, so the app never renders user input as HTML (React
// escapes it) and tokens expire. See docs/ARCHITECTURE.md.
const STORAGE_KEY = 'ai-clinic.session'
const AuthContext = createContext(null)

function readSession() {
  try {
    const session = JSON.parse(localStorage.getItem(STORAGE_KEY))
    if (session?.token && new Date(session.expires_at) > new Date()) return session
  } catch {
    /* ignore malformed storage */
  }
  localStorage.removeItem(STORAGE_KEY)
  return null
}

export function AuthProvider({ children }) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState(readSession)
  const [notice, setNotice] = useState(null)

  const logout = useCallback(
    (message = null) => {
      localStorage.removeItem(STORAGE_KEY)
      setSession(null)
      setNotice(message)
      queryClient.clear()
    },
    [queryClient],
  )

  // Configure during render so the very first queries already carry the token.
  configureApi({
    getToken: () => session?.token,
    onUnauthorized: () => logout('Your session has expired. Please sign in again.'),
  })

  // Log out automatically when the token expires while the app is open.
  useEffect(() => {
    if (!session) return undefined
    const ms = new Date(session.expires_at) - new Date()
    const timer = setTimeout(() => logout('Your session has expired. Please sign in again.'), Math.max(ms, 0))
    return () => clearTimeout(timer)
  }, [session, logout])

  const login = useCallback(async (username, password) => {
    const data = await api.login(username, password)
    const next = { token: data.token, expires_at: data.expires_at, user: data.user }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    setNotice(null)
    setSession(next)
    return data.user
  }, [])

  const value = useMemo(
    () => ({ user: session?.user ?? null, isAuthenticated: Boolean(session), login, logout, notice }),
    [session, login, logout, notice],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}

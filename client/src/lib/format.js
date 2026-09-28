import { APPOINTMENT_TYPES } from './constants'

const typeLabels = Object.fromEntries(APPOINTMENT_TYPES.map((t) => [t.value, t.label]))

export const appointmentTypeLabel = (value) => typeLabels[value] || value

// scheduled_at is clinic-local time without an offset ("2026-05-10T09:30").
export function parseLocal(value) {
  return value ? new Date(value) : null
}

export function formatDateTime(value) {
  const date = parseLocal(value)
  if (!date) return '—'
  return date.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function formatDate(value) {
  const date = parseLocal(value)
  return date ? date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—'
}

export function formatTime(value) {
  const date = parseLocal(value)
  return date ? date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : ''
}

// Server timestamps (created_at) are UTC with a trailing Z.
export function formatTimestamp(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export const percent = (value, digits = 0) =>
  value === null || value === undefined ? '—' : `${(value * 100).toFixed(digits)}%`

export const initials = (name = '') =>
  name
    .replace(/^Dr\.?\s+/i, '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')

export function todayISO() {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60000
  return new Date(now - offset).toISOString().slice(0, 10)
}

export function capitalize(text = '') {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export const APPOINTMENT_TYPES = [
  { value: 'regular_checkup', label: 'Regular check-up' },
  { value: 'follow_up', label: 'Follow-up' },
  { value: 'consultation', label: 'Consultation' },
  { value: 'emergency', label: 'Emergency' },
]

export const STATUSES = [
  { value: 'pending', label: 'Pending' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
]

export const SORT_OPTIONS = [
  { value: 'scheduled_at:desc', label: 'Date (newest first)' },
  { value: 'scheduled_at:asc', label: 'Date (oldest first)' },
  { value: 'patient_name:asc', label: 'Patient (A–Z)' },
  { value: 'confidence:desc', label: 'Model confidence (high–low)' },
  { value: 'created_at:desc', label: 'Recently booked' },
]

export const HOME_ROUTE = { doctor: '/doctor', frontdesk: '/frontdesk' }

export const REPO_URL = 'https://github.com/Shoaib1M/AI-CLINIC'

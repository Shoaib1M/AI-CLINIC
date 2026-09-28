// Server state lives in TanStack Query: caching, loading/error states and
// refetching after mutations. Components never copy server data into local state.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

export const keys = {
  appointments: ['appointments'],
  appointmentList: (params) => ['appointments', 'list', params],
  appointment: (id) => ['appointments', 'detail', String(id)],
  stats: ['appointments', 'stats'],
  model: ['model'],
  patients: (q) => ['patients', q],
  prediction: (symptoms) => ['prediction', symptoms],
}

export const useModelInfo = () =>
  useQuery({ queryKey: keys.model, queryFn: api.modelInfo, staleTime: Infinity })

export const useAppointments = (params) =>
  useQuery({
    queryKey: keys.appointmentList(params),
    queryFn: () => api.listAppointments(params),
    placeholderData: keepPreviousData, // keep the table visible while the next page loads
  })

export const useAppointment = (id) =>
  useQuery({ queryKey: keys.appointment(id), queryFn: () => api.getAppointment(id) })

export const useStats = () => useQuery({ queryKey: keys.stats, queryFn: api.appointmentStats })

export const usePatientSearch = (q) =>
  useQuery({
    queryKey: keys.patients(q),
    queryFn: () => api.searchPatients(q),
    enabled: q.trim().length >= 2,
    staleTime: 30_000,
  })

export const usePredictionPreview = (symptoms) =>
  useQuery({
    queryKey: keys.prediction(symptoms),
    queryFn: () => api.predict(symptoms),
    enabled: symptoms.length > 0,
    staleTime: Infinity, // same symptoms always give the same answer
    retry: false,
  })

function useInvalidateAppointments() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: keys.appointments })
}

export function useCreateAppointment() {
  const invalidate = useInvalidateAppointments()
  return useMutation({ mutationFn: api.createAppointment, onSuccess: invalidate })
}

export function useUpdateAppointment() {
  const queryClient = useQueryClient()
  const invalidate = useInvalidateAppointments()
  return useMutation({
    mutationFn: ({ id, changes }) => api.updateAppointment(id, changes),
    onSuccess: (appointment) => {
      queryClient.setQueryData(keys.appointment(appointment.id), (old) => (old ? { ...old, ...appointment } : old))
      invalidate()
    },
  })
}

export function useCreatePrescription() {
  const invalidate = useInvalidateAppointments()
  return useMutation({ mutationFn: api.createPrescription, onSuccess: invalidate })
}

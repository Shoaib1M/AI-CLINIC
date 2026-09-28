import { useId, useState } from 'react'
import { Search } from 'lucide-react'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { usePatientSearch } from '../hooks/queries'
import { formatDate } from '../lib/format'
import { Spinner } from './ui/States'

/** Typeahead for returning patients (name or phone). */
export function PatientSearch({ onSelect, error }) {
  const id = useId()
  const [query, setQuery] = useState('')
  const debounced = useDebouncedValue(query, 250)
  const { data = [], isFetching, isError } = usePatientSearch(debounced)
  const showResults = debounced.trim().length >= 2

  return (
    <div>
      <label htmlFor={id} className="label">Find patient</label>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
        <input
          id={id}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name or phone number"
          className={`input pl-9 ${error ? 'input-error' : ''}`}
          autoComplete="off"
          aria-describedby={`${id}-help`}
        />
        {isFetching && <Spinner className="absolute top-1/2 right-3 size-4 -translate-y-1/2 text-slate-400" />}
      </div>
      <p id={`${id}-help`} className={error ? 'field-error' : 'hint'}>
        {error || 'Type at least 2 characters.'}
      </p>
      {showResults && (
        <div className="mt-2 overflow-hidden rounded-lg border border-slate-200" aria-live="polite">
          {isError ? (
            <p className="p-3 text-sm text-rose-600">Search failed. Try again.</p>
          ) : data.length === 0 && !isFetching ? (
            <p className="p-3 text-sm text-slate-500">No matching patient. Switch to “New patient” to register them.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.map((patient) => (
                <li key={patient.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(patient)}
                    className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left hover:bg-slate-50 focus-visible:bg-slate-50"
                  >
                    <span>
                      <span className="block text-sm font-medium text-slate-900">{patient.full_name}</span>
                      <span className="block text-xs text-slate-500">{patient.phone}</span>
                    </span>
                    <span className="text-right text-xs text-slate-500">
                      {patient.visit_count} visit{patient.visit_count === 1 ? '' : 's'}
                      {patient.last_visit && <span className="block">Last: {formatDate(patient.last_visit)}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

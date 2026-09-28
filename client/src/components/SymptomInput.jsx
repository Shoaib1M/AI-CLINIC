import { useId, useMemo, useState } from 'react'
import { AlertTriangle, X } from 'lucide-react'
import { normalizeSymptom } from '../lib/symptoms'

const MAX_SUGGESTIONS = 8

/**
 * Chip input with autocomplete from the model's symptom vocabulary.
 * Free text is allowed (clinically relevant symptoms may be outside the
 * vocabulary) but such chips are flagged as "not recognised by the model".
 */
export function SymptomInput({ value, onChange, vocabulary = [], aliases = {}, error, label = 'Symptoms', hint }) {
  const id = useId()
  const listId = `${id}-list`
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [navigated, setNavigated] = useState(false) // arrow keys used on the list
  const known = useMemo(() => new Set(vocabulary), [vocabulary])

  const suggestions = useMemo(() => {
    const needle = normalizeSymptom(text)
    return vocabulary
      .filter((s) => !value.includes(s) && (!needle || s.includes(needle)))
      .sort((a, b) => Number(!a.startsWith(needle)) - Number(!b.startsWith(needle)))
      .slice(0, MAX_SUGGESTIONS)
  }, [text, vocabulary, value])

  const add = (raw) => {
    const symptom = normalizeSymptom(raw, aliases)
    if (symptom && !value.includes(symptom) && symptom.length <= 60) onChange([...value, symptom])
    setText('')
    setActive(0)
    setNavigated(false)
    setOpen(false) // don't leave the list covering the rest of the form; typing reopens it
  }
  const remove = (symptom) => onChange(value.filter((s) => s !== symptom))

  const onKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setNavigated(true)
      setActive((i) => (navigated || text ? Math.min(i + 1, suggestions.length - 1) : 0))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setNavigated(true)
      setActive((i) => Math.max(i - 1, 0))
    } else if (event.key === 'Enter' || event.key === ',') {
      const choice = open && (text || navigated) && suggestions[active] ? suggestions[active] : text
      if (!choice.trim()) return // an empty Enter submits the form as usual
      event.preventDefault()
      add(choice)
    } else if (event.key === 'Backspace' && !text && value.length) {
      remove(value[value.length - 1])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  const unknownCount = value.filter((s) => !known.has(s)).length

  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <div className="relative">
        <div
          className={`input flex min-h-[42px] flex-wrap items-center gap-1.5 py-1.5 ${error ? 'input-error' : ''}`}
          onClick={() => document.getElementById(id)?.focus()}
        >
          {value.map((symptom) => {
            const recognised = known.has(symptom)
            return (
              <span
                key={symptom}
                className={`chip ${recognised ? 'border-brand-200 bg-brand-50 text-brand-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}
                title={recognised ? undefined : 'Not recognised by the model; it will be recorded but ignored for the AI suggestion'}
              >
                {!recognised && <AlertTriangle className="size-3" aria-label="Not recognised by the model" />}
                {symptom}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    remove(symptom)
                  }}
                  className="-mr-0.5 rounded p-0.5 hover:bg-black/5"
                  aria-label={`Remove ${symptom}`}
                >
                  <X className="size-3" />
                </button>
              </span>
            )
          })}
          <input
            id={id}
            role="combobox"
            aria-expanded={open && suggestions.length > 0}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={open && (navigated || text) && suggestions[active] ? `${id}-opt-${active}` : undefined}
            aria-invalid={error ? true : undefined}
            aria-describedby={`${id}-help`}
            value={text}
            onChange={(e) => {
              setText(e.target.value)
              setOpen(true)
              setActive(0)
              setNavigated(false)
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => {
              if (text.trim()) add(text) // keep what was typed when tabbing away
              setOpen(false)
            }}
            onKeyDown={onKeyDown}
            placeholder={value.length ? 'Add another…' : 'Type a symptom, e.g. fever'}
            className="min-w-[8rem] flex-1 border-0 bg-transparent p-1 text-sm outline-none placeholder:text-slate-400"
            autoComplete="off"
          />
        </div>
        {open && suggestions.length > 0 && (
          <ul id={listId} role="listbox" className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
            {suggestions.map((symptom, index) => (
              <li
                key={symptom}
                id={`${id}-opt-${index}`}
                role="option"
                aria-selected={index === active && (navigated || Boolean(text))}
                onMouseDown={(e) => {
                  e.preventDefault()
                  add(symptom)
                }}
                onMouseEnter={() => {
                  setActive(index)
                  setNavigated(true)
                }}
                className={`cursor-pointer px-3 py-1.5 text-sm ${index === active && (navigated || text) ? 'bg-brand-50 text-brand-800' : 'text-slate-700'}`}
              >
                {symptom}
              </li>
            ))}
          </ul>
        )}
      </div>
      <p id={`${id}-help`} className={error ? 'field-error' : 'hint'}>
        {error ||
          (unknownCount
            ? `${unknownCount} symptom(s) are outside the model's vocabulary and will not influence the AI suggestion.`
            : hint || 'Press Enter or comma to add. Suggestions come from the model vocabulary.')}
      </p>
    </div>
  )
}

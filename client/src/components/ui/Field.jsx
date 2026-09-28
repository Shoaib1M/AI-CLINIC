import { cloneElement, useId } from 'react'

// Label + control + hint/error, with the accessibility wiring done once.
export function Field({ label, error, hint, children, className = '', optional = false }) {
  const id = useId()
  const messageId = `${id}-message`
  const control = cloneElement(children, {
    id,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': error || hint ? messageId : undefined,
    className: `${children.props.className || 'input'} ${error ? 'input-error' : ''}`.trim(),
  })
  return (
    <div className={className}>
      <label htmlFor={id} className="label">
        {label}
        {optional && <span className="ml-1 font-normal text-slate-400">(optional)</span>}
      </label>
      {control}
      {error ? (
        <p id={messageId} className="field-error">{error}</p>
      ) : (
        hint && <p id={messageId} className="hint">{hint}</p>
      )}
    </div>
  )
}

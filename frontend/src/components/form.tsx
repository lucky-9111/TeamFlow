import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { useId } from 'react'

export const inputClass =
  'block w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-500'

interface FieldProps {
  label: string
  error?: string
  hint?: string
  children: (props: { id: string; 'aria-invalid': boolean; 'aria-describedby'?: string }) => ReactNode
}

export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId()
  const describedBy = error ? `${id}-err` : hint ? `${id}-hint` : undefined
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-slate-600">
        {label}
      </label>
      {children({ id, 'aria-invalid': !!error, 'aria-describedby': describedBy })}
      {error ? (
        <p id={`${id}-err`} className="mt-1 text-xs text-red-600">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

export function TextField({
  label,
  error,
  hint,
  ...rest
}: { label: string; error?: string; hint?: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(a11y) => <input {...a11y} {...rest} className={`${inputClass} ${rest.className ?? ''}`} />}
    </Field>
  )
}

export function TextArea({
  label,
  error,
  ...rest
}: { label: string; error?: string } & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <Field label={label} error={error}>
      {(a11y) => <textarea {...a11y} {...rest} className={`${inputClass} ${rest.className ?? ''}`} />}
    </Field>
  )
}

export function SelectField({
  label,
  error,
  children,
  ...rest
}: { label: string; error?: string } & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <Field label={label} error={error}>
      {(a11y) => (
        <select {...a11y} {...rest} className={`${inputClass} ${rest.className ?? ''}`}>
          {children}
        </select>
      )}
    </Field>
  )
}

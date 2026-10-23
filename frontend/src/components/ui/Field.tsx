import { useId, type ReactNode } from "react";

interface Props {
  label: string;
  error?: string;
  hint?: string;
  children: (props: { id: string; "aria-invalid": boolean; "aria-describedby"?: string }) => ReactNode;
}

/** Label + control + error text, wired together for screen readers. */
export function Field({ label, error, hint, children }: Props) {
  const id = useId();
  const messageId = `${id}-msg`;
  return (
    <div>
      <label htmlFor={id} className="label">
        {label}
      </label>
      {children({ id, "aria-invalid": !!error, "aria-describedby": error || hint ? messageId : undefined })}
      {error ? (
        <p id={messageId} className="mt-1 text-xs text-red-600">
          {error}
        </p>
      ) : hint ? (
        <p id={messageId} className="mt-1 text-xs text-gray-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
      {message}
    </div>
  );
}

import { AlertCircle, ArrowUp, Bug, Check, CheckSquare, ChevronsUp, Equal, Loader2, ArrowDown, BookOpen } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { ApiError } from '../services/api'
import type { TaskPriority, TaskStatus, TaskType, UserBrief } from '../types'
import { initials, priorityLabel, statusLabel, typeLabel } from '../utils/format'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-indigo-300',
  secondary: 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 disabled:text-slate-400',
  ghost: 'text-slate-600 hover:bg-slate-100 disabled:text-slate-400',
  danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300',
}

export function Button({
  variant = 'secondary',
  loading = false,
  size = 'md',
  className = '',
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean; size?: 'sm' | 'md' }) {
  const pad = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3.5 py-1.5 text-sm'
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors ${pad} ${VARIANTS[variant]} ${className}`}
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

const AVATAR_COLORS = ['bg-indigo-600', 'bg-emerald-600', 'bg-amber-600', 'bg-rose-600', 'bg-sky-600', 'bg-violet-600']

export function Avatar({ user, size = 24 }: { user: Pick<UserBrief, 'id' | 'full_name'>; size?: number }) {
  return (
    <span
      title={user.full_name}
      aria-label={user.full_name}
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-medium text-white ${AVATAR_COLORS[user.id % AVATAR_COLORS.length]}`}
      style={{ width: size, height: size, fontSize: Math.max(9, Math.round(size * 0.4)) }}
    >
      {initials(user.full_name)}
    </span>
  )
}

export function UserChip({ user }: { user: UserBrief | null }) {
  if (!user) return <span className="text-slate-400">Unassigned</span>
  return (
    <span className="inline-flex items-center gap-1.5">
      <Avatar user={user} size={20} />
      <span>{user.full_name}</span>
    </span>
  )
}

const STATUS_STYLE: Record<TaskStatus, string> = {
  todo: 'bg-slate-100 text-slate-700',
  in_progress: 'bg-blue-50 text-blue-700',
  in_review: 'bg-amber-50 text-amber-700',
  done: 'bg-emerald-50 text-emerald-700',
}

export function StatusBadge({ status }: { status: TaskStatus }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium ${STATUS_STYLE[status]}`}>
      {statusLabel(status)}
    </span>
  )
}

const PRIORITY_ICON: Record<TaskPriority, { icon: typeof ArrowUp; color: string }> = {
  low: { icon: ArrowDown, color: 'text-sky-600' },
  medium: { icon: Equal, color: 'text-amber-500' },
  high: { icon: ArrowUp, color: 'text-orange-600' },
  urgent: { icon: ChevronsUp, color: 'text-red-600' },
}

export function PriorityBadge({ priority, label = false }: { priority: TaskPriority; label?: boolean }) {
  const { icon: Icon, color } = PRIORITY_ICON[priority]
  return (
    <span className={`inline-flex items-center gap-1 ${color}`} title={`${priorityLabel(priority)} priority`}>
      <Icon className="h-4 w-4" aria-hidden />
      {label ? <span className="text-slate-700">{priorityLabel(priority)}</span> : <span className="sr-only">{priorityLabel(priority)}</span>}
    </span>
  )
}

const TYPE_ICON: Record<TaskType, { icon: typeof Bug; color: string }> = {
  task: { icon: CheckSquare, color: 'text-sky-600' },
  bug: { icon: Bug, color: 'text-red-600' },
  story: { icon: BookOpen, color: 'text-emerald-600' },
}

export function TypeIcon({ type }: { type: TaskType }) {
  const { icon: Icon, color } = TYPE_ICON[type]
  return (
    <span title={typeLabel(type)} className={color}>
      <Icon className="h-4 w-4" aria-hidden />
      <span className="sr-only">{typeLabel(type)}</span>
    </span>
  )
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-16 text-slate-500">
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
      <span>{label}</span>
    </div>
  )
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-1 px-4 py-12 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      {hint && <p className="max-w-sm text-slate-500">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry?: () => void }) {
  const forbidden = error instanceof ApiError && error.status === 403
  const missing = error instanceof ApiError && error.status === 404
  const title = missing ? 'Not found' : forbidden ? 'Access denied' : 'Something went wrong'
  return (
    <div role="alert" className="flex flex-col items-center gap-2 px-4 py-12 text-center">
      <AlertCircle className="h-6 w-6 text-red-500" aria-hidden />
      <p className="font-medium text-slate-800">{title}</p>
      <p className="max-w-md text-slate-500">{error.message}</p>
      {onRetry && !missing && !forbidden && (
        <Button onClick={onRetry} className="mt-2">
          Try again
        </Button>
      )}
    </div>
  )
}

export function FormError({ message }: { message: string | null | undefined }) {
  if (!message) return null
  return (
    <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      {message}
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-slate-200 bg-white ${className}`}>{children}</section>
}

export function CardHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
      <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
      {action}
    </header>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="truncate text-xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total === 0 ? 0 : Math.round((done / total) * 100)
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Progress"
      >
        <div className="h-full rounded-full bg-emerald-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-9 shrink-0 text-right text-xs text-slate-500">{pct}%</span>
    </div>
  )
}

export function CheckIcon() {
  return <Check className="h-4 w-4" aria-hidden />
}

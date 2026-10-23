import type { ProjectStatus, TaskPriority, TaskStatus, TaskType } from '../types'

export const STATUSES: { value: TaskStatus; label: string }[] = [
  { value: 'todo', label: 'To Do' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'in_review', label: 'In Review' },
  { value: 'done', label: 'Done' },
]
export const PRIORITIES: { value: TaskPriority; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
]
export const TYPES: { value: TaskType; label: string }[] = [
  { value: 'task', label: 'Task' },
  { value: 'bug', label: 'Bug' },
  { value: 'story', label: 'Story' },
]
export const PROJECT_STATUSES: { value: ProjectStatus; label: string }[] = [
  { value: 'active', label: 'Active' },
  { value: 'on_hold', label: 'On hold' },
  { value: 'completed', label: 'Completed' },
]

const labelOf = (list: { value: string; label: string }[], value: string) =>
  list.find((i) => i.value === value)?.label ?? value
export const statusLabel = (v: TaskStatus) => labelOf(STATUSES, v)
export const priorityLabel = (v: TaskPriority) => labelOf(PRIORITIES, v)
export const typeLabel = (v: TaskType) => labelOf(TYPES, v)
export const projectStatusLabel = (v: ProjectStatus) => labelOf(PROJECT_STATUSES, v)

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase() || '?'
}

/** Local calendar date as YYYY-MM-DD (what <input type="date"> and the API use). */
export function todayISO(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Parses a date-only string as a local date, avoiding the UTC off-by-one of `new Date('2026-01-05')`. */
function parseDateOnly(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return parseDateOnly(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatShortDate(iso: string): string {
  return parseDateOnly(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function isOverdue(due: string | null, status: TaskStatus): boolean {
  return !!due && status !== 'done' && due < todayISO()
}

/** Server timestamps are UTC ISO strings. */
export function timeAgo(iso: string, now = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
  })
}

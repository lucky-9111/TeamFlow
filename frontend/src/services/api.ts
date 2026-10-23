import type {
  Activity,
  Comment,
  CurrentUser,
  Dashboard,
  NotificationList,
  Page,
  Project,
  ProjectDetail,
  SearchResults,
  Task,
  TaskFilters,
  TaskInput,
  TeamMember,
  WorkspaceRole,
} from '../types'

const BASE = (import.meta.env.VITE_API_BASE_URL ?? '') + '/api/v1'
const CSRF_COOKIE = 'teamflow_csrf'
const CSRF_HEADER = 'X-CSRF-Token'

export interface FieldError {
  loc: (string | number)[]
  msg: string
}

export class ApiError extends Error {
  status: number
  code: string
  details: FieldError[] | null

  constructor(status: number, code: string, message: string, details: FieldError[] | null = null) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }

  /** Validation messages keyed by field name, for inline form errors. */
  get fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {}
    for (const d of this.details ?? []) {
      const field = String(d.loc[d.loc.length - 1] ?? '')
      if (field && !(field in out)) out[field] = d.msg.replace(/^Value error, /, '')
    }
    return out
  }
}

/** Called when the server says our session is gone, so the UI can send the user to /login. */
let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn
}

function csrfToken(): string {
  const match = document.cookie.split('; ').find((c) => c.startsWith(CSRF_COOKIE + '='))
  return match ? decodeURIComponent(match.split('=')[1]) : ''
}

type Query = Record<string, string | number | boolean | string[] | undefined | null>

function toQuery(params?: Query): string {
  if (!params) return ''
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) continue
    if (Array.isArray(value)) value.forEach((v) => search.append(key, v))
    else search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET') headers[CSRF_HEADER] = csrfToken()

  let response: Response
  try {
    response = await fetch(BASE + path + toQuery(query), {
      method,
      headers,
      credentials: 'include',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the server. Check your connection and try again.')
  }

  if (response.status === 204) return undefined as T

  let payload: unknown = null
  try {
    payload = await response.json()
  } catch {
    /* non-JSON body */
  }

  if (!response.ok) {
    const err = (payload as { error?: { code?: string; message?: string; details?: FieldError[] } } | null)?.error
    const code = err?.code ?? 'http_error'
    // A 401 from /auth/login is just "wrong password"; anywhere else it means the session is gone.
    if (response.status === 401 && path !== '/auth/login') onUnauthorized?.()
    throw new ApiError(
      response.status,
      code,
      err?.message ?? `Request failed (${response.status})`,
      Array.isArray(err?.details) ? err.details : null,
    )
  }
  return payload as T
}

const get = <T>(path: string, query?: Query) => request<T>('GET', path, undefined, query)
const post = <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {})
const patch = <T>(path: string, body: unknown) => request<T>('PATCH', path, body)
const del = (path: string) => request<void>('DELETE', path)

export interface ProjectInput {
  key?: string
  name?: string
  description?: string
  status?: string
  start_date?: string | null
  end_date?: string | null
}

export const api = {
  login: (email: string, password: string) =>
    post<{ user: CurrentUser; csrf_token: string }>('/auth/login', { email, password }),
  logout: () => post<void>('/auth/logout'),
  me: () => get<CurrentUser>('/auth/me'),
  updateMe: (full_name: string) => patch<CurrentUser>('/auth/me', { full_name }),
  changePassword: (current_password: string, new_password: string) =>
    post<void>('/auth/change-password', { current_password, new_password }),

  dashboard: () => get<Dashboard>('/dashboard'),
  search: (q: string) => get<SearchResults>('/search', { q }),
  activity: (query: { project?: string; page?: number; page_size?: number }) =>
    get<Page<Activity>>('/activity', query),
  notifications: () => get<NotificationList>('/notifications'),
  markNotificationRead: (id: number) => post<void>(`/notifications/${id}/read`),
  markAllNotificationsRead: () => post<void>('/notifications/read-all'),
  workspace: () => get<{ name: string }>('/workspace'),
  renameWorkspace: (name: string) => patch<{ name: string }>('/workspace', { name }),

  projects: (query?: { include_archived?: boolean; q?: string }) => get<Project[]>('/projects', query),
  project: (key: string) => get<ProjectDetail>(`/projects/${key}`),
  createProject: (input: ProjectInput) => post<ProjectDetail>('/projects', input),
  updateProject: (key: string, input: ProjectInput) => patch<ProjectDetail>(`/projects/${key}`, input),
  archiveProject: (key: string, archived: boolean) =>
    post<ProjectDetail>(`/projects/${key}/${archived ? 'archive' : 'unarchive'}`),
  addMember: (key: string, user_id: number) => post<ProjectDetail>(`/projects/${key}/members`, { user_id }),
  removeMember: (key: string, user_id: number) => del(`/projects/${key}/members/${user_id}`),

  tasks: (filters: TaskFilters) => get<Page<Task>>('/tasks', filters as Query),
  task: (key: string) => get<Task>(`/tasks/${key}`),
  createTask: (project: string, input: TaskInput) => post<Task>(`/projects/${project}/tasks`, input),
  updateTask: (key: string, input: Partial<TaskInput>) => patch<Task>(`/tasks/${key}`, input),
  deleteTask: (key: string) => del(`/tasks/${key}`),
  comments: (key: string) => get<Comment[]>(`/tasks/${key}/comments`),
  addComment: (key: string, body: string) => post<Comment>(`/tasks/${key}/comments`, { body }),
  taskActivity: (key: string) => get<Activity[]>(`/tasks/${key}/activity`),

  team: () => get<TeamMember[]>('/users'),
  createUser: (input: {
    email: string
    username: string
    full_name: string
    password: string
    workspace_role: WorkspaceRole
  }) => post<TeamMember>('/users', input),
  updateUser: (id: number, input: { full_name?: string; workspace_role?: WorkspaceRole; is_active?: boolean }) =>
    patch<TeamMember>(`/users/${id}`, input),
  resetPassword: (id: number, new_password: string) => post<void>(`/users/${id}/reset-password`, { new_password }),
}

export type TaskStatus = 'todo' | 'in_progress' | 'in_review' | 'done'
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent'
export type TaskType = 'task' | 'bug' | 'story'
export type ProjectStatus = 'active' | 'on_hold' | 'completed'
export type WorkspaceRole = 'admin' | 'member'

export interface UserBrief {
  id: number
  full_name: string
  username: string
}

export interface ProjectRef {
  key: string
  name: string
}

export interface CurrentUser {
  id: number
  email: string
  username: string
  full_name: string
  workspace_role: WorkspaceRole
  must_change_password: boolean
  timezone: string
  last_login_at: string | null
}

export interface Project extends ProjectRef {
  id: number
  description: string
  status: ProjectStatus
  start_date: string | null
  end_date: string | null
  owner: UserBrief
  is_archived: boolean
  task_count: number
  done_count: number
  member_count: number
  created_at: string
}

export interface ProjectDetail extends Project {
  members: UserBrief[]
  can_manage: boolean
}

export interface Task {
  id: number
  key: string
  project: ProjectRef
  title: string
  description: string
  type: TaskType
  status: TaskStatus
  priority: TaskPriority
  assignee: UserBrief | null
  creator: UserBrief
  start_date: string | null
  due_date: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  can_edit: boolean
  can_delete: boolean
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface Comment {
  id: number
  author: UserBrief
  body: string
  created_at: string
}

export interface Activity {
  id: number
  actor: UserBrief
  action: string
  field: string | null
  old_value: string | null
  new_value: string | null
  summary: string
  task_key: string | null
  project_key: string
  created_at: string
}

export interface Notification {
  id: number
  kind: string
  message: string
  task_key: string | null
  read: boolean
  created_at: string
}

export interface NotificationList {
  items: Notification[]
  unread_count: number
}

export interface TeamMember {
  id: number
  email: string
  username: string
  full_name: string
  workspace_role: WorkspaceRole
  is_active: boolean
  open_task_count: number
  projects: ProjectRef[]
  created_at: string
}

export interface Dashboard {
  active_projects: number
  open_tasks: number
  my_open_tasks: number
  overdue_tasks: number
  completed_recently: number
  upcoming_deadlines: Task[]
  my_tasks: Task[]
  recent_activity: Activity[]
}

export interface SearchResults {
  tasks: Task[]
  projects: ProjectRef[]
}

export interface TaskFilters {
  project?: string
  status?: TaskStatus[]
  priority?: TaskPriority[]
  assignee?: string
  q?: string
  overdue?: boolean
  sort?: string
  order?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

export interface TaskInput {
  title: string
  description?: string
  type?: TaskType
  status?: TaskStatus
  priority?: TaskPriority
  assignee_id?: number | null
  start_date?: string | null
  due_date?: string | null
}

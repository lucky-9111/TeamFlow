// Mirrors the backend Pydantic schemas (backend/app/schemas). Keep the two in sync.

export type WorkspaceRole = "admin" | "member";
export type ProjectRole = "manager" | "developer" | "tester" | "designer";
export type ProjectStatus = "active" | "on_hold" | "completed";
export type TaskType = "task" | "bug" | "story";
export type TaskStatus = "todo" | "in_progress" | "in_review" | "done";
export type TaskPriority = "low" | "medium" | "high" | "urgent";
export type NotificationType = "task_assigned" | "task_status" | "task_comment" | "project_added";

export interface CurrentUser {
  id: number;
  email: string;
  username: string;
  full_name: string;
  workspace_role: WorkspaceRole;
  must_change_password: boolean;
  timezone: string;
  last_login_at: string | null;
}

export interface UserBrief {
  id: number;
  username: string;
  full_name: string;
}

export interface TeamMember {
  id: number;
  email: string;
  username: string;
  full_name: string;
  workspace_role: WorkspaceRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  open_task_count: number;
  projects: { key: string; name: string; role: ProjectRole }[];
}

export interface TaskCounts {
  todo: number;
  in_progress: number;
  in_review: number;
  done: number;
  total: number;
  overdue: number;
}

export interface Project {
  id: number;
  key: string;
  name: string;
  description: string;
  status: ProjectStatus;
  start_date: string | null;
  end_date: string | null;
  archived_at: string | null;
  members_can_create_tasks: boolean;
  created_at: string;
  owner: UserBrief;
  my_role: ProjectRole | null;
  member_count: number;
  counts: TaskCounts;
}

export interface ProjectMember {
  user: UserBrief;
  role: ProjectRole;
  is_active: boolean;
  open_task_count: number;
  added_at: string;
}

export interface ProjectDetail extends Project {
  members: ProjectMember[];
  permissions: {
    can_edit: boolean;
    can_manage_members: boolean;
    can_archive: boolean;
    can_create_task: boolean;
  };
}

export interface ProjectRef {
  id: number;
  key: string;
  name: string;
}

export interface Task {
  id: number;
  key: string;
  number: number;
  project: ProjectRef;
  type: TaskType;
  status: TaskStatus;
  priority: TaskPriority;
  title: string;
  description: string;
  reporter: UserBrief;
  assignee: UserBrief | null;
  start_date: string | null;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  is_overdue: boolean;
  allowed_transitions: TaskStatus[];
}

export interface TaskDetail extends Task {
  permissions: { can_edit: boolean; can_assign: boolean; can_delete: boolean; can_comment: boolean };
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Board {
  project: ProjectRef;
  columns: { status: TaskStatus; tasks: Task[] }[];
}

export interface Comment {
  id: number;
  author: UserBrief;
  body: string;
  created_at: string;
  edited_at: string | null;
  can_edit: boolean;
}

export interface ActivityEvent {
  id: number;
  actor: UserBrief;
  action: string;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  target: string;
  project_key: string | null;
  task_key: string | null;
  created_at: string;
}

export interface Dashboard {
  stats: {
    active_projects: number;
    open_tasks: number;
    my_open_tasks: number;
    overdue_tasks: number;
    completed_last_7_days: number;
  };
  my_tasks: Task[];
  upcoming: Task[];
  recently_completed: Task[];
  recent_activity: ActivityEvent[];
  projects: { key: string; name: string; done: number; total: number }[];
}

export interface Notification {
  id: number;
  type: NotificationType;
  message: string;
  actor_name: string | null;
  project_key: string | null;
  task_key: string | null;
  read: boolean;
  created_at: string;
}

export interface SearchResults {
  projects: { key: string; name: string }[];
  tasks: Task[];
}

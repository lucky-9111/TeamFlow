import { keepPreviousData, useQuery, type QueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import type {
  ActivityEvent,
  Board,
  Comment,
  Dashboard,
  Notification,
  Page,
  Project,
  ProjectDetail,
  SearchResults,
  Task,
  TaskDetail,
  TeamMember,
} from "../types/api";

export interface TaskFilters {
  project?: string;
  status?: string[];
  priority?: string[];
  type?: string[];
  assignee?: string;
  q?: string;
  overdue?: boolean;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export const useDashboard = () =>
  useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<Dashboard>("/dashboard") });

export const useProjects = (includeArchived = false) =>
  useQuery({
    queryKey: ["projects", { includeArchived }],
    queryFn: () => api.get<Project[]>("/projects", { include_archived: includeArchived }),
  });

export const useProject = (key: string | undefined) =>
  useQuery({
    queryKey: ["project", key],
    queryFn: () => api.get<ProjectDetail>(`/projects/${key}`),
    enabled: !!key,
  });

export const useBoard = (key: string | undefined, filters: { assignee?: string; q?: string; priority?: string[] }) =>
  useQuery({
    queryKey: ["board", key, filters],
    queryFn: () => api.get<Board>(`/projects/${key}/board`, filters),
    enabled: !!key,
    placeholderData: keepPreviousData,
  });

export const useTasks = (filters: TaskFilters) =>
  useQuery({
    queryKey: ["tasks", filters],
    queryFn: () => api.get<Page<Task>>("/tasks", { ...filters }),
    placeholderData: keepPreviousData,
  });

export const useTask = (key: string | undefined) =>
  useQuery({ queryKey: ["task", key], queryFn: () => api.get<TaskDetail>(`/tasks/${key}`), enabled: !!key });

export const useComments = (key: string) =>
  useQuery({ queryKey: ["task", key, "comments"], queryFn: () => api.get<Comment[]>(`/tasks/${key}/comments`) });

export const useTaskActivity = (key: string) =>
  useQuery({
    queryKey: ["task", key, "activity"],
    queryFn: () => api.get<ActivityEvent[]>(`/tasks/${key}/activity`),
  });

export const useTeam = (includeInactive = false) =>
  useQuery({
    queryKey: ["users", { includeInactive }],
    queryFn: () => api.get<TeamMember[]>("/users", { include_inactive: includeInactive }),
  });

export const useActivity = (project: string | undefined, page: number) =>
  useQuery({
    queryKey: ["activity", { project, page }],
    queryFn: () => api.get<Page<ActivityEvent>>("/activity", { project, page }),
    placeholderData: keepPreviousData,
  });

export const useNotifications = (enabled: boolean) =>
  useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<Notification[]>("/notifications"),
    enabled,
  });

export const useUnreadCount = () =>
  useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => api.get<{ count: number }>("/notifications/unread-count"),
    refetchInterval: 30_000,
  });

export const useSearch = (q: string) =>
  useQuery({
    queryKey: ["search", q],
    queryFn: () => api.get<SearchResults>("/search", { q }),
    enabled: q.trim().length >= 2,
    placeholderData: keepPreviousData,
  });

export const useWorkspace = () =>
  useQuery({ queryKey: ["workspace"], queryFn: () => api.get<{ name: string }>("/workspace") });

/** Anything that shows tasks or counts can be stale after a task changes. */
export function invalidateTaskViews(qc: QueryClient, taskKey?: string) {
  if (taskKey) qc.invalidateQueries({ queryKey: ["task", taskKey] });
  for (const key of ["board", "tasks", "dashboard", "project", "projects", "activity", "users", "search"]) {
    qc.invalidateQueries({ queryKey: [key] });
  }
}

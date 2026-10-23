import type { ProjectRole, ProjectStatus, TaskPriority, TaskStatus, TaskType } from "../types/api";

export const STATUSES: TaskStatus[] = ["todo", "in_progress", "in_review", "done"];
export const PRIORITIES: TaskPriority[] = ["urgent", "high", "medium", "low"];
export const TYPES: TaskType[] = ["task", "story", "bug"];
export const PROJECT_ROLES: ProjectRole[] = ["manager", "developer", "tester", "designer"];
export const PROJECT_STATUSES: ProjectStatus[] = ["active", "on_hold", "completed"];

export const STATUS_LABEL: Record<TaskStatus, string> = {
  todo: "To Do",
  in_progress: "In Progress",
  in_review: "In Review",
  done: "Done",
};

export const PRIORITY_LABEL: Record<TaskPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};

export const TYPE_LABEL: Record<TaskType, string> = { task: "Task", bug: "Bug", story: "Story" };

export const ROLE_LABEL: Record<ProjectRole, string> = {
  manager: "Manager",
  developer: "Developer",
  tester: "Tester",
  designer: "Designer",
};

export const PROJECT_STATUS_LABEL: Record<ProjectStatus, string> = {
  active: "Active",
  on_hold: "On hold",
  completed: "Completed",
};

/** Field names in activity rows, made readable. */
export const FIELD_LABEL: Record<string, string> = {
  title: "title",
  description: "description",
  type: "type",
  priority: "priority",
  start_date: "start date",
  due_date: "due date",
  status: "status",
  assignee: "assignee",
  name: "name",
  end_date: "end date",
  members_can_create_tasks: "task creation setting",
  workspace_role: "workspace role",
};

export function valueLabel(field: string | null, value: string | null): string {
  if (value === null || value === "") return "none";
  if (field === "status" && value in STATUS_LABEL) return STATUS_LABEL[value as TaskStatus];
  if (field === "priority" && value in PRIORITY_LABEL) return PRIORITY_LABEL[value as TaskPriority];
  if (field === "type" && value in TYPE_LABEL) return TYPE_LABEL[value as TaskType];
  if (value in ROLE_LABEL) return ROLE_LABEL[value as ProjectRole];
  if (value in PROJECT_STATUS_LABEL) return PROJECT_STATUS_LABEL[value as ProjectStatus];
  return value;
}

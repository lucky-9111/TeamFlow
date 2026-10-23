import { Link } from "react-router-dom";
import type { Task } from "../../types/api";
import { Avatar } from "../ui/Avatar";
import { DueDate, PriorityIcon, StatusBadge, TypeIcon } from "./TaskBits";

/** Compact one-line task used in dashboards and lists. */
export function TaskRow({ task, showProject = true }: { task: Task; showProject?: boolean }) {
  return (
    <Link
      to={`/tasks/${task.key}`}
      className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 focus-visible:bg-gray-50"
    >
      <TypeIcon type={task.type} />
      <span className="w-16 shrink-0 text-xs font-medium text-gray-500">{task.key}</span>
      <span className="min-w-0 flex-1 truncate text-gray-900">{task.title}</span>
      {showProject && <span className="hidden truncate text-xs text-gray-500 md:inline">{task.project.name}</span>}
      <DueDate due={task.due_date} overdue={task.is_overdue} done={task.status === "done"} />
      <span className="hidden sm:inline">
        <StatusBadge status={task.status} />
      </span>
      <PriorityIcon priority={task.priority} />
      <Avatar user={task.assignee} />
    </Link>
  );
}

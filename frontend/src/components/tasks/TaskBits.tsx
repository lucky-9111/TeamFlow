import { ArrowDown, ArrowUp, Bookmark, Bug, CheckSquare, ChevronsUp, Equal } from "lucide-react";
import type { TaskPriority, TaskStatus, TaskType } from "../../types/api";
import { dueLabel } from "../../utils/format";
import { PRIORITY_LABEL, STATUS_LABEL, TYPE_LABEL } from "../../utils/labels";

const statusStyle: Record<TaskStatus, string> = {
  todo: "bg-gray-100 text-gray-700",
  in_progress: "bg-blue-50 text-blue-700",
  in_review: "bg-amber-50 text-amber-800",
  done: "bg-green-50 text-green-700",
};

export function StatusBadge({ status }: { status: TaskStatus }) {
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${statusStyle[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}

const priorityIcon = {
  urgent: { Icon: ChevronsUp, cls: "text-red-600" },
  high: { Icon: ArrowUp, cls: "text-orange-500" },
  medium: { Icon: Equal, cls: "text-amber-500" },
  low: { Icon: ArrowDown, cls: "text-sky-600" },
};

export function PriorityIcon({ priority, withLabel = false }: { priority: TaskPriority; withLabel?: boolean }) {
  const { Icon, cls } = priorityIcon[priority];
  return (
    <span className="inline-flex items-center gap-1 text-xs text-gray-700" title={`${PRIORITY_LABEL[priority]} priority`}>
      <Icon className={`h-4 w-4 ${cls}`} aria-hidden />
      {withLabel ? PRIORITY_LABEL[priority] : <span className="sr-only">{PRIORITY_LABEL[priority]} priority</span>}
    </span>
  );
}

const typeIcon = {
  task: { Icon: CheckSquare, cls: "text-sky-600" },
  story: { Icon: Bookmark, cls: "text-emerald-600" },
  bug: { Icon: Bug, cls: "text-red-600" },
};

export function TypeIcon({ type }: { type: TaskType }) {
  const { Icon, cls } = typeIcon[type];
  return (
    <span title={TYPE_LABEL[type]} className="inline-flex">
      <Icon className={`h-4 w-4 ${cls}`} aria-hidden />
      <span className="sr-only">{TYPE_LABEL[type]}</span>
    </span>
  );
}

export function DueDate({ due, overdue, done }: { due: string | null; overdue: boolean; done: boolean }) {
  const label = dueLabel(due, done);
  if (!label) return null;
  return (
    <span className={`text-xs ${overdue ? "font-medium text-red-600" : "text-gray-500"}`}>{label}</span>
  );
}

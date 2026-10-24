import { Link } from "react-router-dom";
import type { ActivityEvent } from "../types/api";
import { timeAgo } from "../utils/format";
import { FIELD_LABEL, valueLabel } from "../utils/labels";
import { Avatar } from "./ui/Avatar";

/** Turns an activity row into "<verb> <target>", e.g. "moved from To Do to In Progress". */
function describe(e: ActivityEvent): string {
  const field = e.field ? (FIELD_LABEL[e.field] ?? e.field) : "";
  const from = valueLabel(e.field, e.old_value);
  const to = valueLabel(e.field, e.new_value);
  switch (e.action) {
    case "task_created":
      return "created";
    case "task_deleted":
      return "deleted";
    case "status_changed":
      return `moved from ${from} to ${to}:`;
    case "task_assigned":
      return e.new_value ? `assigned to ${e.new_value}:` : "unassigned:";
    case "task_updated":
      return e.field === "description" ? "updated the description of" : `changed ${field} from ${from} to ${to} on`;
    case "comment_added":
      return "commented on";
    case "project_created":
      return "created project";
    case "project_updated":
      return e.field === "description" ? "updated the description of" : `changed ${field} to ${to} on`;
    case "project_archived":
      return "archived";
    case "project_unarchived":
      return "restored";
    case "member_added":
      return `added ${e.new_value} to`;
    case "member_removed":
      return `removed ${e.old_value} from`;
    case "member_role_changed":
      return `made ${e.field} ${to} in`;
    case "user_created":
      return "added team member";
    case "user_deactivated":
      return "deactivated";
    case "user_activated":
      return "reactivated";
    case "user_role_changed":
      return `set the workspace role to ${to} for`;
    default:
      return e.action.replace(/_/g, " ");
  }
}

/** One line of history. On a task's own page the task name is redundant, so it can be hidden. */
export function ActivityItem({ event, showTarget = true }: { event: ActivityEvent; showTarget?: boolean }) {
  const href = event.task_key ? `/tasks/${event.task_key}` : event.project_key ? `/projects/${event.project_key}` : null;
  const verb = describe(event);
  return (
    <li className="flex gap-3 px-4 py-3">
      <Avatar user={event.actor} size="sm" />
      <div className="min-w-0 flex-1 text-sm text-gray-700">
        <span className="font-medium text-gray-900">{event.actor.full_name}</span>{" "}
        {showTarget ? verb : verb.replace(/( on| of| in|:)$/, "")}{" "}
        {showTarget &&
          (href ? (
            <Link to={href} className="font-medium text-gray-900 hover:underline">
              {event.target}
            </Link>
          ) : (
            <span className="font-medium text-gray-900">{event.target}</span>
          ))}
        <div className="text-xs text-gray-400">{timeAgo(event.created_at)}</div>
      </div>
    </li>
  );
}

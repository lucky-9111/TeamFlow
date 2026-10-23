"""Central role -> action matrix. Routes never inline role logic; services call `require()`.

Two roles: workspace `admin` (full access) and `member`. A member's access to a project comes from
a `project_members` row, and edits to a specific task depend on whether they are its assignee or
creator. Callers pass those facts as keyword arguments.
"""

from enum import StrEnum

from app.core.errors import PermissionDenied
from app.models.user import User


class Action(StrEnum):
    # Admin only
    WORKSPACE_MANAGE = "workspace.manage"
    USER_MANAGE = "user.manage"
    PROJECT_CREATE = "project.create"
    PROJECT_EDIT = "project.edit"
    PROJECT_ARCHIVE = "project.archive"
    PROJECT_MEMBERS_MANAGE = "project.members.manage"
    ACTIVITY_VIEW_ALL = "activity.view_all"

    # Project members
    PROJECT_VIEW = "project.view"
    TASK_CREATE = "task.create"
    TASK_COMMENT = "task.comment"

    # Record level: admin, or a project member who is the task's assignee or creator
    TASK_EDIT = "task.edit"
    TASK_DELETE = "task.delete"


ADMIN_ONLY = frozenset(
    {
        Action.WORKSPACE_MANAGE,
        Action.USER_MANAGE,
        Action.PROJECT_CREATE,
        Action.PROJECT_EDIT,
        Action.PROJECT_ARCHIVE,
        Action.PROJECT_MEMBERS_MANAGE,
        Action.ACTIVITY_VIEW_ALL,
    }
)
MEMBER_OF_PROJECT = frozenset({Action.PROJECT_VIEW, Action.TASK_CREATE, Action.TASK_COMMENT})


def can(
    user: User,
    action: Action,
    *,
    is_project_member: bool = False,
    is_assignee: bool = False,
    is_creator: bool = False,
) -> bool:
    if not user.is_active:
        return False
    if user.is_admin:
        return True
    if action in ADMIN_ONLY:
        return False
    if not is_project_member:
        return False
    if action in MEMBER_OF_PROJECT:
        return True
    if action == Action.TASK_EDIT:
        return is_assignee or is_creator
    if action == Action.TASK_DELETE:
        return is_creator
    return False


def require(user: User, action: Action, **facts: bool) -> None:
    if not can(user, action, **facts):
        raise PermissionDenied("You do not have permission to perform this action")

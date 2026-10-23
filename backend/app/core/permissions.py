"""Central role → action matrix.

Coarse permissions are decided here from the user's workspace role and project role.
Rules that depend on the specific record (e.g. "the task is assigned to me", "members may create
tasks in this project") are evaluated in the services, on top of these checks.
Routes never inline role logic; they call services, which call `require()`.
"""

from enum import StrEnum

from app.core.errors import PermissionDenied
from app.models.enums import ProjectRole
from app.models.user import User


class Action(StrEnum):
    # Workspace-level
    WORKSPACE_MANAGE = "workspace.manage"
    USER_MANAGE = "user.manage"
    PROJECT_CREATE = "project.create"
    PROJECT_ARCHIVE = "project.archive"
    ACTIVITY_VIEW_ALL = "activity.view_all"

    # Project-level
    PROJECT_VIEW = "project.view"
    PROJECT_EDIT = "project.edit"
    PROJECT_MEMBERS_MANAGE = "project.members.manage"
    TASK_CREATE = "task.create"  # non-managers are additionally gated by members_can_create_tasks
    TASK_EDIT_ANY = "task.edit_any"  # edit and reassign any task; assignee/reporter edit their own
    TASK_DELETE = "task.delete"
    TASK_REVIEW = "task.review"  # In Review -> Done / back to In Progress, reopen Done
    TASK_TRANSITION_ANY = "task.transition_any"
    TASK_COMMENT = "task.comment"
    COMMENT_MODERATE = "comment.moderate"  # edit/delete other people's comments


WORKSPACE_ADMIN_ACTIONS = frozenset(
    {
        Action.WORKSPACE_MANAGE,
        Action.USER_MANAGE,
        Action.PROJECT_CREATE,
        Action.PROJECT_ARCHIVE,
        Action.ACTIVITY_VIEW_ALL,
    }
)

_EVERY_MEMBER = frozenset({Action.PROJECT_VIEW, Action.TASK_CREATE, Action.TASK_COMMENT})

PROJECT_ROLE_ACTIONS: dict[ProjectRole, frozenset[Action]] = {
    ProjectRole.MANAGER: _EVERY_MEMBER
    | {
        Action.PROJECT_EDIT,
        Action.PROJECT_MEMBERS_MANAGE,
        Action.TASK_EDIT_ANY,
        Action.TASK_DELETE,
        Action.TASK_REVIEW,
        Action.TASK_TRANSITION_ANY,
        Action.COMMENT_MODERATE,
    },
    ProjectRole.DEVELOPER: _EVERY_MEMBER,
    ProjectRole.TESTER: _EVERY_MEMBER | {Action.TASK_REVIEW},
    ProjectRole.DESIGNER: _EVERY_MEMBER,
}


def can(user: User, action: Action, project_role: ProjectRole | None = None) -> bool:
    """`project_role` is the user's role in the project in question (None if not a member)."""
    if not user.is_active:
        return False
    if user.is_admin:
        return True  # admins have implicit full access to every project
    if action in WORKSPACE_ADMIN_ACTIONS:
        return False
    if project_role is None:
        return False
    return action in PROJECT_ROLE_ACTIONS[project_role]


def require(user: User, action: Action, project_role: ProjectRole | None = None) -> None:
    if not can(user, action, project_role):
        raise PermissionDenied("You do not have permission to perform this action")

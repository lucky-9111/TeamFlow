"""Central role → action matrix.

Coarse permissions are decided here from the user's workspace role and project role.
Rules that depend on the specific record (e.g. "the issue is assigned to me", "the bug-creation
setting is enabled for this project") are evaluated in the services, on top of these checks.
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
    ISSUE_CREATE_PLANNING = "issue.create_planning"  # Epic / Story / Task
    ISSUE_CREATE_BUG = "issue.create_bug"
    ISSUE_CREATE_SUBTASK = "issue.create_subtask"
    ISSUE_EDIT_ANY = "issue.edit_any"
    ISSUE_EDIT_BUGS = "issue.edit_bugs"
    ISSUE_EDIT_ASSIGNED = "issue.edit_assigned"
    ISSUE_DELETE = "issue.delete"
    ISSUE_REVIEW = "issue.review"  # In Review → Done, reopen Done
    ISSUE_COMMENT = "issue.comment"
    ISSUE_ATTACH = "issue.attach"
    WORKLOG_CREATE = "worklog.create"
    CONTENT_MODERATE = "content.moderate"  # delete others' comments / attachments
    SPRINT_MANAGE = "sprint.manage"
    REPORT_VIEW = "report.view"


WORKSPACE_ADMIN_ACTIONS = frozenset(
    {
        Action.WORKSPACE_MANAGE,
        Action.USER_MANAGE,
        Action.PROJECT_CREATE,
        Action.PROJECT_ARCHIVE,
        Action.ACTIVITY_VIEW_ALL,
    }
)

_EVERY_MEMBER = frozenset(
    {
        Action.PROJECT_VIEW,
        Action.ISSUE_CREATE_SUBTASK,
        Action.ISSUE_EDIT_ASSIGNED,
        Action.ISSUE_COMMENT,
        Action.ISSUE_ATTACH,
        Action.WORKLOG_CREATE,
        Action.REPORT_VIEW,
    }
)

PROJECT_ROLE_ACTIONS: dict[ProjectRole, frozenset[Action]] = {
    ProjectRole.MANAGER: _EVERY_MEMBER
    | {
        Action.PROJECT_EDIT,
        Action.PROJECT_MEMBERS_MANAGE,
        Action.ISSUE_CREATE_PLANNING,
        Action.ISSUE_CREATE_BUG,
        Action.ISSUE_EDIT_ANY,
        Action.ISSUE_EDIT_BUGS,
        Action.ISSUE_DELETE,
        Action.ISSUE_REVIEW,
        Action.CONTENT_MODERATE,
        Action.SPRINT_MANAGE,
    },
    # Developer bug creation is additionally gated by the project's allow_developer_bugs setting.
    ProjectRole.DEVELOPER: _EVERY_MEMBER | {Action.ISSUE_CREATE_BUG},
    ProjectRole.TESTER: _EVERY_MEMBER
    | {Action.ISSUE_CREATE_BUG, Action.ISSUE_EDIT_BUGS, Action.ISSUE_REVIEW},
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

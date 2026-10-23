"""Import every model here so Base.metadata is complete for Alembic and tests."""

from app.models.base import Base
from app.models.notification import Notification
from app.models.project import Project, ProjectMember
from app.models.task import Activity, Task, TaskComment
from app.models.user import AuthSession, LoginAttempt, User
from app.models.workspace import Workspace

__all__ = [
    "Activity",
    "AuthSession",
    "Base",
    "LoginAttempt",
    "Notification",
    "Project",
    "ProjectMember",
    "Task",
    "TaskComment",
    "User",
    "Workspace",
]

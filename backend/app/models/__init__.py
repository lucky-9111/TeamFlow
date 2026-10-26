"""Import every model here so Base.metadata is complete for Alembic and tests."""

from app.models.base import Base
from app.models.notification import Notification
from app.models.project import Project, ProjectMember
from app.models.task import (
    ActivityEvent,
    Task,
    TaskComment,
    TaskDependency,
    TaskLabel,
    TaskReminder,
    TaskWatcher,
)
from app.models.user import AuthSession, LoginAttempt, User
from app.models.workspace import Workspace

__all__ = [
    "ActivityEvent",
    "AuthSession",
    "Base",
    "LoginAttempt",
    "Notification",
    "Project",
    "ProjectMember",
    "Task",
    "TaskComment",
    "TaskDependency",
    "TaskLabel",
    "TaskReminder",
    "TaskWatcher",
    "User",
    "Workspace",
]

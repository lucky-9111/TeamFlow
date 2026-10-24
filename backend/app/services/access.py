"""Loading projects and tasks *through* the current user's access.

Every lookup by key goes through here. A user who is not a member gets 404, not 403, so knowing a
key or ID never reveals that a project or task exists (prevents IDOR).
"""

import re
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound
from app.core.permissions import Action, can, require
from app.models.enums import ProjectRole
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User

_TASK_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]{1,9})-(\d{1,9})$")


@dataclass
class ProjectAccess:
    project: Project
    role: ProjectRole | None  # None for an admin who is not a member

    def can(self, user: User, action: Action) -> bool:
        return can(user, action, self.role)

    def require(self, user: User, action: Action) -> None:
        require(user, action, self.role)


@dataclass
class TaskAccess(ProjectAccess):
    task: Task


def member_role(db: Session, project_id: int, user_id: int) -> ProjectRole | None:
    return db.scalar(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )


def accessible_project_ids(user: User) -> Select:
    """Subquery of project ids the user can see (admins see every project)."""
    if user.is_admin:
        return select(Project.id)
    return select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)


def get_project(db: Session, user: User, key: str) -> ProjectAccess:
    project = db.scalar(select(Project).where(Project.key == key.upper()))
    if project is None:
        raise NotFound("Project not found")
    role = member_role(db, project.id, user.id)
    if role is None and not user.is_admin:
        raise NotFound("Project not found")
    return ProjectAccess(project=project, role=role)


def get_task(db: Session, user: User, task_key: str) -> TaskAccess:
    match = _TASK_KEY_RE.match(task_key)
    if not match:
        raise NotFound("Task not found")
    project_key, number = match.group(1).upper(), int(match.group(2))
    task = db.scalar(
        select(Task)
        .join(Project, Task.project_id == Project.id)
        .where(Project.key == project_key, Task.number == number)
    )
    if task is None:
        raise NotFound("Task not found")
    role = member_role(db, task.project_id, user.id)
    if role is None and not user.is_admin:
        raise NotFound("Task not found")
    return TaskAccess(project=task.project, role=role, task=task)


def ensure_not_archived(project: Project) -> None:
    if project.archived_at is not None:
        raise Conflict(
            "This project is archived. Unarchive it before making changes.", code="project_archived"
        )

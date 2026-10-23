"""Read-side aggregates: dashboard, team page, activity feed, notifications."""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Action, require
from app.core.security import hash_password
from app.models.base import utcnow
from app.models.enums import ProjectStatus, TaskStatus, WorkspaceRole
from app.models.notification import Notification
from app.models.project import Project, ProjectMember
from app.models.task import Activity, Task
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.common import Page
from app.schemas.task import ActivityOut, DashboardOut, NotificationList, NotificationOut
from app.schemas.user import ProjectRef, TeamMember
from app.services import auth as auth_service
from app.services import projects, tasks

OPEN = Task.status != TaskStatus.DONE


def dashboard(db: Session, user: User) -> DashboardOut:
    today = projects.today()
    visible = projects.accessible_project_ids(db, user)

    def scoped(stmt):
        stmt = stmt.join(Project, Project.id == Task.project_id).where(Project.archived_at.is_(None))
        return stmt if visible is None else stmt.where(Task.project_id.in_(visible))

    def count(*conditions) -> int:
        return db.scalar(scoped(select(func.count(Task.id))).where(*conditions)) or 0

    project_stmt = select(func.count(Project.id)).where(
        Project.archived_at.is_(None), Project.status == ProjectStatus.ACTIVE
    )
    if visible is not None:
        project_stmt = project_stmt.where(Project.id.in_(visible))

    member_of = tasks.member_project_ids(db, user)
    load = tasks.LOAD

    def fetch(stmt, limit):
        return [tasks.task_out(t, user, member_of) for t in db.scalars(stmt.options(*load).limit(limit))]

    upcoming = fetch(
        scoped(select(Task))
        .where(OPEN, Task.due_date >= today, Task.due_date <= tasks.week_ahead())
        .order_by(Task.due_date, Task.id),
        6,
    )
    mine = fetch(
        scoped(select(Task))
        .where(OPEN, Task.assignee_id == user.id)
        .order_by(Task.due_date.asc().nulls_last(), Task.id.desc()),
        6,
    )
    return DashboardOut(
        active_projects=db.scalar(project_stmt) or 0,
        open_tasks=count(OPEN),
        my_open_tasks=count(OPEN, Task.assignee_id == user.id),
        overdue_tasks=count(OPEN, Task.due_date < today),
        completed_recently=count(Task.completed_at >= utcnow() - timedelta(days=7)),
        upcoming_deadlines=upcoming,
        my_tasks=mine,
        recent_activity=list_activity(db, user, page_size=8).items,
    )


def list_activity(
    db: Session, user: User, *, project: str | None = None, page: int = 1, page_size: int = 30
) -> Page[ActivityOut]:
    stmt = select(Activity).join(Project, Project.id == Activity.project_id)
    visible = projects.accessible_project_ids(db, user)
    if visible is not None:
        stmt = stmt.where(Activity.project_id.in_(visible))
    if project:
        stmt = stmt.where(Project.key == project.upper())
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(
        stmt.options(*tasks.ACTIVITY_LOAD)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return Page[ActivityOut](
        items=[tasks.activity_out(r) for r in rows], total=total, page=page, page_size=page_size
    )


def team(db: Session, viewer: User) -> list[TeamMember]:
    """Admins see everyone; members see active colleagues, limited to projects they share."""
    stmt = select(User).order_by(User.full_name)
    if not viewer.is_admin:
        stmt = stmt.where(User.is_active.is_(True))
    users = db.scalars(stmt).all()

    shown = projects.accessible_project_ids(db, viewer)
    pm_stmt = (
        select(ProjectMember.user_id, Project)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(Project.archived_at.is_(None))
        .order_by(Project.key)
    )
    open_stmt = (
        select(Task.assignee_id, func.count(Task.id))
        .join(Project, Project.id == Task.project_id)
        .where(OPEN, Task.assignee_id.is_not(None), Project.archived_at.is_(None))
        .group_by(Task.assignee_id)
    )
    if shown is not None:
        pm_stmt = pm_stmt.where(ProjectMember.project_id.in_(shown))
        open_stmt = open_stmt.where(Task.project_id.in_(shown))

    projects_by_user: dict[int, list[ProjectRef]] = {}
    for user_id, project in db.execute(pm_stmt):
        projects_by_user.setdefault(user_id, []).append(ProjectRef.model_validate(project))
    open_counts = dict(db.execute(open_stmt).all())

    return [
        TeamMember(
            id=u.id,
            email=u.email,
            username=u.username,
            full_name=u.full_name,
            workspace_role=u.workspace_role,
            is_active=u.is_active,
            open_task_count=open_counts.get(u.id, 0),
            projects=projects_by_user.get(u.id, []),
            created_at=u.created_at,
        )
        for u in users
    ]


# ---------------------------------------------------------------- user admin


def update_user(db: Session, actor: User, user_id: int, changes: dict) -> User:
    require(actor, Action.USER_MANAGE)
    target = db.get(User, user_id)
    if target is None:
        raise NotFound("User not found")
    for field in ("full_name", "workspace_role", "is_active"):
        if field in changes and changes[field] is None:
            raise ValidationFailed(f"{field} cannot be null")

    demoting = changes.get("workspace_role") == WorkspaceRole.MEMBER and target.is_admin
    deactivating = changes.get("is_active") is False and target.is_active
    if (demoting or deactivating) and target.id == actor.id:
        raise Conflict("You cannot demote or deactivate your own account", code="self_lockout")
    for field, value in changes.items():
        setattr(target, field, value.strip() if field == "full_name" else value)
    if deactivating:
        auth_service.revoke_all_sessions(db, target.id)
        # Their open work goes back to the pool rather than sitting with someone who cannot log in.
        db.query(Task).filter(Task.assignee_id == target.id).update({Task.assignee_id: None})
    db.commit()
    return target


def reset_password(db: Session, actor: User, user_id: int, new_password: str) -> None:
    require(actor, Action.USER_MANAGE)
    target = db.get(User, user_id)
    if target is None:
        raise NotFound("User not found")
    target.password_hash = hash_password(new_password)
    target.must_change_password = True
    auth_service.revoke_all_sessions(db, target.id)
    db.commit()


def get_workspace(db: Session) -> Workspace:
    workspace = db.scalar(select(Workspace))
    if workspace is None:
        raise NotFound("Workspace has not been set up. Run the create-admin command.")
    return workspace


def rename_workspace(db: Session, actor: User, name: str) -> Workspace:
    require(actor, Action.WORKSPACE_MANAGE)
    workspace = get_workspace(db)
    workspace.name = name.strip()
    db.commit()
    return workspace


# ---------------------------------------------------------------- notifications


def list_notifications(db: Session, user: User, *, unread_only: bool = False) -> NotificationList:
    stmt = select(Notification).where(Notification.recipient_id == user.id)
    unread = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == user.id, Notification.read_at.is_(None)
        )
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    rows = db.scalars(stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(50)).all()
    task_ids = {n.task_id for n in rows if n.task_id}
    keys: dict[int, str] = {}
    if task_ids:
        for t in db.scalars(select(Task).where(Task.id.in_(task_ids)).options(selectinload(Task.project))):
            keys[t.id] = t.key
    items = [
        NotificationOut(
            id=n.id,
            kind=n.kind,
            message=n.message,
            task_key=keys.get(n.task_id),
            read=n.read_at is not None,
            created_at=n.created_at,
        )
        for n in rows
    ]
    return NotificationList(items=items, unread_count=unread or 0)


def mark_read(db: Session, user: User, notification_id: int | None) -> None:
    stmt = select(Notification).where(Notification.recipient_id == user.id, Notification.read_at.is_(None))
    if notification_id is not None:
        stmt = stmt.where(Notification.id == notification_id)
    now = utcnow()
    found = db.scalars(stmt).all()
    if notification_id is not None and not found:
        # Already read or not theirs: indistinguishable on purpose.
        existing = db.scalar(
            select(Notification.id).where(
                Notification.id == notification_id, Notification.recipient_id == user.id
            )
        )
        if existing is None:
            raise NotFound("Notification not found")
    for n in found:
        n.read_at = now
    db.commit()

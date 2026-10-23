from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.base import utcnow
from app.models.enums import TaskStatus
from app.models.project import Project
from app.models.task import ActivityEvent, Task
from app.models.user import User
from app.schemas.common import Page
from app.schemas.dashboard import (
    Dashboard,
    DashboardStats,
    ProjectProgress,
    SearchProject,
    SearchResults,
)
from app.schemas.tasks import ActivityOut
from app.services import activity, tasks
from app.services.access import accessible_project_ids

_EAGER = (selectinload(Task.project), selectinload(Task.assignee), selectinload(Task.reporter))


def _visible_tasks(user: User):
    """Tasks in non-archived projects the user can see."""
    return (
        select(Task)
        .join(Project, Task.project_id == Project.id)
        .where(Task.project_id.in_(accessible_project_ids(user)), Project.archived_at.is_(None))
    )


def _count(db: Session, stmt) -> int:
    return db.scalar(select(func.count()).select_from(stmt.subquery()))


def dashboard(db: Session, user: User) -> Dashboard:
    today = activity.today_for(user)
    week_ago = utcnow() - timedelta(days=7)
    visible = _visible_tasks(user)
    open_ = visible.where(Task.status != TaskStatus.DONE)
    mine = open_.where(Task.assignee_id == user.id)
    overdue = open_.where(Task.due_date < today)
    completed = visible.where(Task.status == TaskStatus.DONE, Task.completed_at >= week_ago)

    projects = list(
        db.scalars(
            select(Project)
            .where(Project.id.in_(accessible_project_ids(user)), Project.archived_at.is_(None))
            .order_by(Project.name)
        )
    )
    counts = tasks.task_counts(db, [p.id for p in projects], today)

    def rows(stmt, *order, limit=8):
        return [
            tasks.to_out(t, today) for t in db.scalars(stmt.options(*_EAGER).order_by(*order).limit(limit))
        ]

    return Dashboard(
        stats=DashboardStats(
            active_projects=len(projects),
            open_tasks=_count(db, open_),
            my_open_tasks=_count(db, mine),
            overdue_tasks=_count(db, overdue),
            completed_last_7_days=_count(db, completed),
        ),
        my_tasks=rows(mine, Task.due_date.is_(None), Task.due_date, Task.updated_at.desc()),
        upcoming=rows(
            open_.where(Task.due_date >= today, Task.due_date <= today + timedelta(days=14)), Task.due_date
        ),
        recently_completed=rows(completed, Task.completed_at.desc(), limit=5),
        recent_activity=activity_feed(db, user, project=None, page=1, page_size=10).items,
        projects=[
            ProjectProgress(key=p.key, name=p.name, done=counts[p.id].done, total=counts[p.id].total)
            for p in projects
        ],
    )


def activity_feed(
    db: Session, user: User, *, project: str | None, page: int, page_size: int
) -> Page[ActivityOut]:
    page_size = max(1, min(page_size, 100))
    stmt = select(ActivityEvent).outerjoin(Project, ActivityEvent.project_id == Project.id)
    # Admins also see workspace-level events (users created, roles changed), which have no project.
    if not user.is_admin:
        stmt = stmt.where(ActivityEvent.project_id.in_(accessible_project_ids(user)))
    if project:
        stmt = stmt.where(Project.key == project.upper())
    total = _count(db, stmt)
    events = db.scalars(
        stmt.options(
            selectinload(ActivityEvent.actor),
            selectinload(ActivityEvent.project),
            selectinload(ActivityEvent.task).selectinload(Task.project),
        )
        .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(items=[activity.to_out(e) for e in events], total=total, page=page, page_size=page_size)


def task_history(db: Session, task: Task) -> list[ActivityOut]:
    events = db.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.task_id == task.id)
        .options(selectinload(ActivityEvent.actor), selectinload(ActivityEvent.project))
        .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
        .limit(200)
    )
    return [activity.to_out(e) for e in events]


def search(db: Session, user: User, q: str) -> SearchResults:
    q = q.strip()
    if not q:
        return SearchResults(projects=[], tasks=[])
    projects = db.scalars(
        select(Project)
        .where(
            Project.id.in_(accessible_project_ids(user)),
            Project.archived_at.is_(None),
            Project.name.icontains(q, autoescape=True) | Project.key.icontains(q, autoescape=True),
        )
        .order_by(Project.name)
        .limit(5)
    )
    found = tasks.list_tasks(
        db, user, project=None, sort="updated", descending=True, page=1, page_size=10, q=q
    )
    return SearchResults(
        projects=[SearchProject(key=p.key, name=p.name) for p in projects],
        tasks=found.items,
    )

import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Action, require
from app.models.base import utcnow
from app.models.enums import TaskStatus
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectDetail, ProjectOut, ProjectUpdate
from app.schemas.user import UserBrief
from app.services import activity

KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")


@dataclass
class ProjectAccess:
    project: Project
    is_member: bool


def accessible_project_ids(db: Session, user: User):
    """Subquery of project ids the user may see (None means every project, for admins)."""
    if user.is_admin:
        return None
    return select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)


def is_member(db: Session, project_id: int, user_id: int) -> bool:
    return (
        db.scalar(
            select(ProjectMember.id).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
            )
        )
        is not None
    )


def get_project(db: Session, user: User, key: str) -> ProjectAccess:
    """Missing and inaccessible projects both return 404 so keys can't be probed."""
    project = db.scalar(select(Project).where(Project.key == key.upper()))
    if project is None:
        raise NotFound("Project not found")
    member = is_member(db, project.id, user.id)
    if not member and not user.is_admin:
        raise NotFound("Project not found")
    return ProjectAccess(project, member)


def _stats(db: Session, project_ids: list[int]) -> dict[int, tuple[int, int, int]]:
    if not project_ids:
        return {}
    tasks = db.execute(
        select(
            Task.project_id,
            func.count(Task.id),
            func.coalesce(func.sum(case((Task.status == TaskStatus.DONE, 1), else_=0)), 0),
        )
        .where(Task.project_id.in_(project_ids))
        .group_by(Task.project_id)
    ).all()
    members = dict(
        db.execute(
            select(ProjectMember.project_id, func.count(ProjectMember.id))
            .where(ProjectMember.project_id.in_(project_ids))
            .group_by(ProjectMember.project_id)
        ).all()
    )
    by_task = {pid: (total, done) for pid, total, done in tasks}
    return {pid: (*by_task.get(pid, (0, 0)), members.get(pid, 0)) for pid in project_ids}


def _out(project: Project, stats: tuple[int, int, int]) -> dict:
    total, done, members = stats
    return dict(
        id=project.id,
        key=project.key,
        name=project.name,
        description=project.description,
        status=project.status,
        start_date=project.start_date,
        end_date=project.end_date,
        owner=UserBrief.model_validate(project.owner),
        is_archived=project.archived_at is not None,
        task_count=total,
        done_count=int(done),
        member_count=members,
        created_at=project.created_at,
    )


def to_out(db: Session, project: Project) -> ProjectOut:
    return ProjectOut(**_out(project, _stats(db, [project.id])[project.id]))


def to_detail(db: Session, user: User, project: Project) -> ProjectDetail:
    members = db.scalars(
        select(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id == project.id)
        .order_by(User.full_name)
    ).all()
    return ProjectDetail(
        **_out(project, _stats(db, [project.id])[project.id]),
        members=[UserBrief.model_validate(m) for m in members],
        can_manage=user.is_admin,
    )


def list_projects(db: Session, user: User, *, include_archived: bool, q: str | None) -> list[ProjectOut]:
    stmt = select(Project).options(selectinload(Project.owner)).order_by(Project.name)
    visible = accessible_project_ids(db, user)
    if visible is not None:
        stmt = stmt.where(Project.id.in_(visible))
    if not include_archived:
        stmt = stmt.where(Project.archived_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Project.name.ilike(like), Project.key.ilike(like)))
    projects = db.scalars(stmt).all()
    stats = _stats(db, [p.id for p in projects])
    return [ProjectOut(**_out(p, stats[p.id])) for p in projects]


def create_project(db: Session, actor: User, data: ProjectCreate) -> Project:
    require(actor, Action.PROJECT_CREATE)
    key = data.key.strip().upper()
    if not KEY_RE.match(key):
        raise ValidationFailed(
            "Project key must be 2-10 characters: letters and digits, starting with a letter"
        )
    if db.scalar(select(Project.id).where(Project.key == key)):
        raise Conflict("A project with this key already exists", code="key_taken")
    project = Project(
        key=key,
        name=data.name.strip(),
        description=data.description,
        status=data.status,
        start_date=data.start_date,
        end_date=data.end_date,
        owner_id=actor.id,
    )
    project.memberships.append(ProjectMember(user_id=actor.id))
    db.add(project)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("A project with this key already exists", code="key_taken") from exc
    activity.record(
        db, project_id=project.id, actor=actor, action="project.created", summary=f"created project {key}"
    )
    db.commit()
    return project


def update_project(db: Session, actor: User, project: Project, data: ProjectUpdate) -> Project:
    require(actor, Action.PROJECT_EDIT)
    changes = data.model_dump(exclude_unset=True)
    for field in ("name", "description", "status"):
        if field in changes and changes[field] is None:
            raise ValidationFailed(f"{field} cannot be null")
    start = changes.get("start_date", project.start_date)
    end = changes.get("end_date", project.end_date)
    if start and end and end < start:
        raise ValidationFailed("end_date must not be before start_date")
    for field, value in changes.items():
        setattr(project, field, value.strip() if field == "name" else value)
    if changes:
        activity.record(
            db,
            project_id=project.id,
            actor=actor,
            action="project.updated",
            summary=f"updated project {project.key}",
        )
    db.commit()
    return project


def set_archived(db: Session, actor: User, project: Project, archived: bool) -> Project:
    require(actor, Action.PROJECT_ARCHIVE)
    project.archived_at = utcnow() if archived else None
    activity.record(
        db,
        project_id=project.id,
        actor=actor,
        action="project.archived" if archived else "project.unarchived",
        summary=f"{'archived' if archived else 'restored'} project {project.key}",
    )
    db.commit()
    return project


def add_member(db: Session, actor: User, project: Project, user_id: int) -> None:
    require(actor, Action.PROJECT_MEMBERS_MANAGE)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise NotFound("User not found")
    if is_member(db, project.id, user_id):
        raise Conflict("User is already a member of this project", code="already_member")
    db.add(ProjectMember(project_id=project.id, user_id=user_id))
    activity.record(
        db,
        project_id=project.id,
        actor=actor,
        action="project.member_added",
        summary=f"added {user.full_name} to {project.key}",
    )
    db.commit()


def remove_member(db: Session, actor: User, project: Project, user_id: int) -> None:
    require(actor, Action.PROJECT_MEMBERS_MANAGE)
    membership = db.scalar(
        select(ProjectMember).where(ProjectMember.project_id == project.id, ProjectMember.user_id == user_id)
    )
    if membership is None:
        raise NotFound("Member not found")
    if user_id == project.owner_id:
        raise ValidationFailed("The project owner cannot be removed")
    user = db.get(User, user_id)
    # Tasks stay with the project but lose an assignee who can no longer see them.
    db.execute(
        update(Task)
        .where(Task.project_id == project.id, Task.assignee_id == user_id)
        .values(assignee_id=None)
    )
    db.delete(membership)
    activity.record(
        db,
        project_id=project.id,
        actor=actor,
        action="project.member_removed",
        summary=f"removed {user.full_name} from {project.key}",
    )
    db.commit()


def today() -> date:
    return utcnow().date()

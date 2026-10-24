from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Action, require
from app.models.base import utcnow
from app.models.enums import NotificationType, ProjectRole
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.projects import (
    AddMemberRequest,
    CreateProjectRequest,
    ProjectDetail,
    ProjectMemberOut,
    ProjectOut,
    ProjectPermissions,
    UpdateMemberRequest,
    UpdateProjectRequest,
)
from app.schemas.users import UserBrief
from app.services import activity, tasks
from app.services.access import ProjectAccess, accessible_project_ids, ensure_not_archived, member_role
from app.services.notifications import notify


def _out(project: Project, role: ProjectRole | None, member_count: int, counts) -> ProjectOut:
    return ProjectOut.model_validate(project).model_copy(
        update={"my_role": role, "member_count": member_count, "counts": counts}
    )


def list_projects(db: Session, user: User, *, include_archived: bool) -> list[ProjectOut]:
    stmt = (
        select(Project)
        .where(Project.id.in_(accessible_project_ids(user)))
        .options(selectinload(Project.owner))
    )
    if not include_archived:
        stmt = stmt.where(Project.archived_at.is_(None))
    projects = list(db.scalars(stmt.order_by(Project.archived_at.is_not(None), Project.name)))
    ids = [p.id for p in projects]
    roles = dict(
        db.execute(
            select(ProjectMember.project_id, ProjectMember.role).where(
                ProjectMember.user_id == user.id, ProjectMember.project_id.in_(ids)
            )
        ).all()
    )
    member_counts = dict(
        db.execute(
            select(ProjectMember.project_id, func.count())
            .where(ProjectMember.project_id.in_(ids))
            .group_by(ProjectMember.project_id)
        ).all()
    )
    counts = tasks.task_counts(db, ids, activity.today_for(user))
    return [_out(p, roles.get(p.id), member_counts.get(p.id, 0), counts[p.id]) for p in projects]


def _members(db: Session, project: Project) -> list[ProjectMemberOut]:
    rows = list(
        db.scalars(
            select(ProjectMember)
            .where(ProjectMember.project_id == project.id)
            .options(selectinload(ProjectMember.user))
        )
    )
    open_counts = tasks.open_task_counts(db, [m.user_id for m in rows], project.id)
    rows.sort(key=lambda m: (list(ProjectRole).index(m.role), m.user.full_name.lower()))
    return [
        ProjectMemberOut(
            user=UserBrief.model_validate(m.user),
            role=m.role,
            is_active=m.user.is_active,
            open_task_count=open_counts.get(m.user_id, 0),
            added_at=m.created_at,
        )
        for m in rows
    ]


def detail(db: Session, user: User, access: ProjectAccess) -> ProjectDetail:
    project = access.project
    members = _members(db, project)
    counts = tasks.task_counts(db, [project.id], activity.today_for(user))[project.id]
    archived = project.archived_at is not None
    can_create = (
        not archived
        and access.can(user, Action.TASK_CREATE)
        and (project.members_can_create_tasks or access.can(user, Action.TASK_EDIT_ANY))
    )
    base = _out(project, access.role, len(members), counts)
    return ProjectDetail(
        **base.model_dump(),
        members=members,
        permissions=ProjectPermissions(
            can_edit=not archived and access.can(user, Action.PROJECT_EDIT),
            can_manage_members=not archived and access.can(user, Action.PROJECT_MEMBERS_MANAGE),
            can_archive=access.can(user, Action.PROJECT_ARCHIVE),
            can_create_task=can_create,
        ),
    )


def create_project(db: Session, user: User, body: CreateProjectRequest) -> ProjectAccess:
    require(user, Action.PROJECT_CREATE)
    if db.scalar(select(Project.id).where(Project.key == body.key)):
        raise Conflict(f"The project key {body.key} is already in use", code="project_key_taken")
    project = Project(**body.model_dump(), owner=user)
    db.add(project)
    db.flush()
    # The creator manages the project they create.
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.MANAGER))
    activity.record(db, user, "project_created", project=project)
    db.commit()
    return ProjectAccess(project=project, role=ProjectRole.MANAGER)


def update_project(db: Session, user: User, access: ProjectAccess, body: UpdateProjectRequest) -> None:
    project = access.project
    ensure_not_archived(project)
    access.require(user, Action.PROJECT_EDIT)
    changes = body.model_dump(exclude_unset=True)
    for field in ("name", "status", "members_can_create_tasks"):
        if field in changes and changes[field] is None:
            raise ValidationFailed(f"{field} cannot be empty")
    start = changes.get("start_date", project.start_date)
    end = changes.get("end_date", project.end_date)
    if start and end and end < start:
        raise ValidationFailed("End date cannot be before the start date")
    for field, value in changes.items():
        if field == "description":
            value = value or ""
        old = getattr(project, field)
        if value == old:
            continue
        setattr(project, field, value)
        logged_old, logged_new = (None, None) if field == "description" else (old, value)
        activity.record(
            db, user, "project_updated", project=project, field=field, old=logged_old, new=logged_new
        )
    db.commit()


def set_archived(db: Session, user: User, access: ProjectAccess, archived: bool) -> None:
    access.require(user, Action.PROJECT_ARCHIVE)
    project = access.project
    if (project.archived_at is not None) == archived:
        return
    project.archived_at = utcnow() if archived else None
    activity.record(db, user, "project_archived" if archived else "project_unarchived", project=project)
    db.commit()


def add_member(db: Session, user: User, access: ProjectAccess, body: AddMemberRequest) -> None:
    project = access.project
    ensure_not_archived(project)
    access.require(user, Action.PROJECT_MEMBERS_MANAGE)
    new_member = db.get(User, body.user_id)
    if new_member is None or not new_member.is_active:
        raise NotFound("User not found or deactivated")
    if member_role(db, project.id, new_member.id) is not None:
        raise Conflict(f"{new_member.full_name} is already a member of this project", code="already_member")
    db.add(ProjectMember(project_id=project.id, user_id=new_member.id, role=body.role))
    activity.record(db, user, "member_added", project=project, field="member", new=new_member.full_name)
    notify(
        db,
        [new_member],
        user,
        NotificationType.PROJECT_ADDED,
        f"{user.full_name} added you to {project.name}",
        project=project,
    )
    db.commit()


def _membership(db: Session, project: Project, user_id: int) -> ProjectMember:
    member = db.scalar(
        select(ProjectMember).where(ProjectMember.project_id == project.id, ProjectMember.user_id == user_id)
    )
    if member is None:
        raise NotFound("This user is not a member of the project")
    return member


def _ensure_manager_remains(db: Session, project: Project, leaving: ProjectMember) -> None:
    if leaving.role != ProjectRole.MANAGER:
        return
    managers = db.scalar(
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == project.id, ProjectMember.role == ProjectRole.MANAGER)
    )
    if managers <= 1:
        raise Conflict(
            "A project needs at least one manager. Make someone else manager first.", code="last_manager"
        )


def update_member(
    db: Session, user: User, access: ProjectAccess, user_id: int, body: UpdateMemberRequest
) -> None:
    project = access.project
    ensure_not_archived(project)
    access.require(user, Action.PROJECT_MEMBERS_MANAGE)
    member = _membership(db, project, user_id)
    if member.role == body.role:
        return
    if body.role != ProjectRole.MANAGER:
        _ensure_manager_remains(db, project, member)
    old = member.role
    member.role = body.role
    activity.record(
        db, user, "member_role_changed", project=project, field=member.user.full_name, old=old, new=body.role
    )
    db.commit()


def remove_member(db: Session, user: User, access: ProjectAccess, user_id: int) -> None:
    project = access.project
    ensure_not_archived(project)
    access.require(user, Action.PROJECT_MEMBERS_MANAGE)
    member = _membership(db, project, user_id)
    _ensure_manager_remains(db, project, member)
    tasks.unassign_open_tasks(db, user, project, user_id)
    activity.record(db, user, "member_removed", project=project, field="member", old=member.user.full_name)
    db.delete(member)
    db.commit()

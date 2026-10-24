import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Action, require
from app.core.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, hash_password
from app.models.enums import WorkspaceRole
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.users import (
    CreateUserRequest,
    MemberProject,
    TeamMember,
    UpdateProfileRequest,
    UpdateUserRequest,
)
from app.services import activity, tasks
from app.services.auth import normalize_email, revoke_all_sessions

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,31}$")


def validate_password_policy(password: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValidationFailed(
            f"Password must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters"
        )


def create_user(
    db: Session,
    *,
    email: str,
    username: str,
    full_name: str,
    password: str,
    workspace_role: WorkspaceRole = WorkspaceRole.MEMBER,
    must_change_password: bool = True,
) -> User:
    """Create a user. The caller commits. Permission checks happen before this is called."""
    email = normalize_email(email)
    username = username.strip().lower()
    full_name = full_name.strip()
    if not USERNAME_RE.match(username):
        raise ValidationFailed("Username must be 3-32 characters: lowercase letters, digits, '.', '_' or '-'")
    if not full_name:
        raise ValidationFailed("Full name is required")
    validate_password_policy(password)

    if db.scalar(select(User.id).where(User.email == email)):
        raise Conflict("A user with this email already exists", code="email_taken")
    if db.scalar(select(User.id).where(User.username == username)):
        raise Conflict("This username is already taken", code="username_taken")

    user = User(
        email=email,
        username=username,
        full_name=full_name,
        password_hash=hash_password(password),
        workspace_role=workspace_role,
        must_change_password=must_change_password,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------- team management (admin)


def _admin_count(db: Session) -> int:
    return db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.workspace_role == WorkspaceRole.ADMIN, User.is_active.is_(True))
    )


def _get(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("User not found")
    return user


def list_team(
    db: Session, *, q: str | None, include_inactive: bool, user_id: int | None = None
) -> list[TeamMember]:
    stmt = select(User)
    if user_id is not None:
        stmt = stmt.where(User.id == user_id)
    if not include_inactive:
        stmt = stmt.where(User.is_active.is_(True))
    if q:
        stmt = stmt.where(
            User.full_name.icontains(q, autoescape=True)
            | User.email.icontains(q, autoescape=True)
            | User.username.icontains(q, autoescape=True)
        )
    users = list(db.scalars(stmt.order_by(User.is_active.desc(), User.full_name)))
    ids = [u.id for u in users]
    open_counts = tasks.open_task_counts(db, ids)
    memberships: dict[int, list[MemberProject]] = {}
    rows = db.execute(
        select(ProjectMember.user_id, Project.key, Project.name, ProjectMember.role)
        .join(Project, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id.in_(ids), Project.archived_at.is_(None))
        .order_by(Project.name)
    )
    for user_id, key, name, role in rows:
        memberships.setdefault(user_id, []).append(MemberProject(key=key, name=name, role=role))
    return [
        TeamMember.model_validate(u).model_copy(
            update={"open_task_count": open_counts.get(u.id, 0), "projects": memberships.get(u.id, [])}
        )
        for u in users
    ]


def admin_create_user(db: Session, admin: User, body: CreateUserRequest) -> User:
    require(admin, Action.USER_MANAGE)
    user = create_user(
        db,
        email=body.email,
        username=body.username,
        full_name=body.full_name,
        password=body.temporary_password,
        workspace_role=body.workspace_role,
        must_change_password=True,
    )
    activity.record(db, admin, "user_created", target=user.full_name)
    db.commit()
    return user


def admin_update_user(db: Session, admin: User, user_id: int, body: UpdateUserRequest) -> User:
    require(admin, Action.USER_MANAGE)
    user = _get(db, user_id)
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.workspace_role is not None and body.workspace_role != user.workspace_role:
        if user.is_admin and _admin_count(db) <= 1:
            raise Conflict("The workspace needs at least one admin", code="last_admin")
        activity.record(
            db,
            admin,
            "user_role_changed",
            target=user.full_name,
            field="workspace_role",
            old=user.workspace_role,
            new=body.workspace_role,
        )
        user.workspace_role = body.workspace_role
    db.commit()
    return user


def set_active(db: Session, admin: User, user_id: int, active: bool) -> User:
    require(admin, Action.USER_MANAGE)
    user = _get(db, user_id)
    if user.is_active == active:
        return user
    if not active:
        if user.id == admin.id:
            raise Conflict("You cannot deactivate your own account", code="self_deactivate")
        if user.is_admin and _admin_count(db) <= 1:
            raise Conflict("The workspace needs at least one admin", code="last_admin")
        revoke_all_sessions(db, user.id)
    user.is_active = active
    activity.record(db, admin, "user_activated" if active else "user_deactivated", target=user.full_name)
    db.commit()
    return user


def reset_password(db: Session, admin: User, user_id: int, temporary_password: str) -> None:
    require(admin, Action.USER_MANAGE)
    user = _get(db, user_id)
    validate_password_policy(temporary_password)
    user.password_hash = hash_password(temporary_password)
    user.must_change_password = True
    revoke_all_sessions(db, user.id)
    db.commit()


def update_profile(db: Session, user: User, body: UpdateProfileRequest) -> User:
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.timezone is not None:
        try:
            ZoneInfo(body.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValidationFailed("Unknown timezone") from exc
        user.timezone = body.timezone
    db.commit()
    return user


def get_workspace(db: Session) -> Workspace:
    return db.scalar(select(Workspace).order_by(Workspace.id)) or Workspace(name="TeamFlow", settings={})


def update_workspace(db: Session, admin: User, name: str) -> Workspace:
    require(admin, Action.WORKSPACE_MANAGE)
    workspace = db.scalar(select(Workspace).order_by(Workspace.id))
    if workspace is None:
        workspace = Workspace(name=name, settings={})
        db.add(workspace)
    workspace.name = name
    db.commit()
    return workspace

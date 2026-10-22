import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, ValidationFailed
from app.core.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, hash_password
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.services.auth import normalize_email

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

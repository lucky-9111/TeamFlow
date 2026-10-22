from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import PermissionDenied
from app.core.permissions import Action, require
from app.core.security import tokens_match
from app.models.user import AuthSession, User
from app.services import auth as auth_service

DB = Annotated[Session, Depends(get_db)]

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def client_ip(request: Request) -> str | None:
    # Behind Nginx, run uvicorn with --proxy-headers so request.client reflects X-Forwarded-For.
    return request.client.host if request.client else None


def get_auth_session(request: Request, db: DB) -> AuthSession:
    settings = get_settings()
    session = auth_service.resolve_session(db, request.cookies.get(settings.session_cookie_name))
    if request.method not in _SAFE_METHODS:
        csrf = request.headers.get(settings.csrf_header_name)
        if not csrf or not tokens_match(csrf, session.csrf_hash):
            raise PermissionDenied("Missing or invalid CSRF token", code="csrf_failed")
    return session


CurrentSession = Annotated[AuthSession, Depends(get_auth_session)]


def get_user_allow_password_change(session: CurrentSession) -> User:
    """Authenticated user, even if they still have to replace a temporary password."""
    return session.user


def get_current_user(session: CurrentSession) -> User:
    if session.user.must_change_password:
        raise PermissionDenied(
            "You must change your temporary password before continuing", code="password_change_required"
        )
    return session.user


CurrentUserAllowPending = Annotated[User, Depends(get_user_allow_password_change)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_action(action: Action):
    """Dependency factory for workspace-level actions (project actions are checked in services)."""

    def _dep(user: CurrentUser) -> User:
        require(user, action)
        return user

    return Depends(_dep)

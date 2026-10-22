from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotAuthenticated, TooManyRequests, ValidationFailed
from app.core.security import (
    hash_password,
    hash_token,
    new_token,
    password_needs_rehash,
    verify_password,
)
from app.models.base import utcnow
from app.models.user import AuthSession, LoginAttempt, User

# Refresh last_seen_at at most this often, so ordinary GETs don't all write to the DB.
_LAST_SEEN_GRANULARITY = timedelta(minutes=1)
# Per-IP limit is looser than per-account so one office NAT doesn't lock everyone out.
_IP_FAILURE_MULTIPLIER = 4


@dataclass
class IssuedSession:
    user: User
    session: AuthSession
    token: str
    csrf_token: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _recent_failures(db: Session, column, value: str, since) -> int:
    return db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(column == value, LoginAttempt.success.is_(False), LoginAttempt.created_at >= since)
    )


def _check_throttle(db: Session, identifier: str, ip: str | None) -> None:
    settings = get_settings()
    since = utcnow() - timedelta(minutes=settings.login_lockout_minutes)
    if _recent_failures(db, LoginAttempt.identifier, identifier, since) >= settings.login_max_failures:
        raise TooManyRequests("Too many failed login attempts. Try again later.")
    if ip and _recent_failures(db, LoginAttempt.ip_address, ip, since) >= (
        settings.login_max_failures * _IP_FAILURE_MULTIPLIER
    ):
        raise TooManyRequests("Too many failed login attempts. Try again later.")


def login(db: Session, email: str, password: str, ip: str | None, user_agent: str | None) -> IssuedSession:
    identifier = normalize_email(email)
    _check_throttle(db, identifier, ip)

    user = db.scalar(select(User).where(User.email == identifier))
    password_ok = verify_password(password, user.password_hash if user else None)

    if not user or not password_ok or not user.is_active:
        db.add(LoginAttempt(identifier=identifier, ip_address=ip, success=False))
        db.commit()
        # One generic message: don't reveal whether the account exists or is deactivated.
        raise NotAuthenticated("Invalid email or password", code="invalid_credentials")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    db.add(LoginAttempt(identifier=identifier, ip_address=ip, success=True))
    # A successful login clears the account's failure streak.
    db.execute(
        delete(LoginAttempt).where(LoginAttempt.identifier == identifier, LoginAttempt.success.is_(False))
    )

    issued = _issue_session(db, user, ip, user_agent)
    user.last_login_at = utcnow()
    db.commit()
    return issued


def _issue_session(db: Session, user: User, ip: str | None, user_agent: str | None) -> IssuedSession:
    settings = get_settings()
    token, csrf_token = new_token(), new_token()
    now = utcnow()
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_hash=hash_token(csrf_token),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=settings.session_max_days),
        ip_address=ip,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    db.flush()
    return IssuedSession(user=user, session=session, token=token, csrf_token=csrf_token)


def resolve_session(db: Session, token: str | None) -> AuthSession:
    """Return the live session for a cookie token, or raise NotAuthenticated."""
    if not token:
        raise NotAuthenticated("Authentication required")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if session is None or session.revoked_at is not None:
        raise NotAuthenticated("Authentication required")

    now = utcnow()
    idle_limit = timedelta(hours=get_settings().session_idle_hours)
    if session.expires_at <= now or session.last_seen_at + idle_limit <= now:
        raise NotAuthenticated("Your session has expired. Please log in again.", code="session_expired")
    if not session.user.is_active:
        raise NotAuthenticated("Authentication required")

    if now - session.last_seen_at >= _LAST_SEEN_GRANULARITY:
        session.last_seen_at = now
        db.commit()
    return session


def logout(db: Session, session: AuthSession) -> None:
    session.revoked_at = utcnow()
    db.commit()


def rotate_csrf(db: Session, session: AuthSession) -> str:
    csrf_token = new_token()
    session.csrf_hash = hash_token(csrf_token)
    db.commit()
    return csrf_token


def revoke_all_sessions(db: Session, user_id: int, *, except_session_id: int | None = None) -> None:
    stmt = update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    if except_session_id is not None:
        stmt = stmt.where(AuthSession.id != except_session_id)
    db.execute(stmt.values(revoked_at=utcnow()))


def change_password(db: Session, session: AuthSession, current_password: str, new_password: str) -> None:
    user = session.user
    if not verify_password(current_password, user.password_hash):
        raise ValidationFailed("Current password is incorrect", code="invalid_password")
    if verify_password(new_password, user.password_hash):
        raise ValidationFailed("New password must be different from the current password")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    # Sign out every other device; the session making the change stays valid.
    revoke_all_sessions(db, user.id, except_session_id=session.id)
    db.commit()

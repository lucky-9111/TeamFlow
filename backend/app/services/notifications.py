from collections.abc import Iterable

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models.base import utcnow
from app.models.enums import NotificationType
from app.models.notification import Notification
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.dashboard import NotificationOut


def notify(
    db: Session,
    recipients: Iterable[User | None],
    actor: User,
    type_: NotificationType,
    message: str,
    *,
    project: Project | None = None,
    task: Task | None = None,
) -> None:
    """Queue in-app notifications. The actor never notifies themselves; the caller commits."""
    project = project or (task.project if task else None)
    seen: set[int] = set()
    for user in recipients:
        if user is None or user.id == actor.id or user.id in seen or not user.is_active:
            continue
        seen.add(user.id)
        db.add(
            Notification(
                recipient_id=user.id,
                actor_id=actor.id,
                type=type_,
                project_id=project.id if project else None,
                task_id=task.id if task else None,
                message=message[:255],
            )
        )


def to_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        type=n.type,
        message=n.message,
        actor_name=n.actor.full_name if n.actor else None,
        project_key=n.project.key if n.project else None,
        task_key=n.task.key if n.task else None,
        read=n.read_at is not None,
        created_at=n.created_at,
    )


def list_for(db: Session, user: User, *, unread_only: bool, limit: int) -> list[NotificationOut]:
    stmt = select(Notification).where(Notification.recipient_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    rows = db.scalars(stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit))
    return [to_out(n) for n in rows]


def unread_count(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.recipient_id == user.id, Notification.read_at.is_(None))
    )


def mark_read(db: Session, user: User, notification_id: int) -> None:
    n = db.get(Notification, notification_id)
    if n is None or n.recipient_id != user.id:
        raise NotFound("Notification not found")
    if n.read_at is None:
        n.read_at = utcnow()
        db.commit()


def mark_all_read(db: Session, user: User) -> None:
    db.execute(
        update(Notification)
        .where(Notification.recipient_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    db.commit()

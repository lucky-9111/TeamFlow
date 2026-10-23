from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.task import Activity, Task
from app.models.user import User


def record(
    db: Session,
    *,
    project_id: int,
    actor: User,
    action: str,
    summary: str,
    task: Task | None = None,
    field: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> Activity:
    """Add a history row to the caller's transaction (the caller commits)."""
    entry = Activity(
        project_id=project_id,
        task_id=task.id if task else None,
        actor_id=actor.id,
        action=action,
        field=field,
        old_value=(old_value or None) and old_value[:255],
        new_value=(new_value or None) and new_value[:255],
        summary=summary[:300],
    )
    db.add(entry)
    return entry


def notify(
    db: Session, *, recipient_id: int | None, actor: User, task: Task, kind: str, message: str
) -> None:
    """In-app notification; skipped when the actor would only be notifying themselves."""
    if recipient_id is None or recipient_id == actor.id:
        return
    db.add(
        Notification(
            recipient_id=recipient_id, actor_id=actor.id, task_id=task.id, kind=kind, message=message[:300]
        )
    )

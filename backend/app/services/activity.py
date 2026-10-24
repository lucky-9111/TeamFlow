from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.project import Project
from app.models.task import ActivityEvent, Task
from app.models.user import User
from app.schemas.tasks import ActivityOut
from app.schemas.users import UserBrief


def today_for(user: User) -> date:
    """'Today' in the user's timezone, so a task due today isn't overdue at 05:30 IST."""
    try:
        tz = ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    return utcnow().astimezone(tz).date()


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date | datetime):
        return value.isoformat()
    return str(value)[:255]


def record(
    db: Session,
    actor: User,
    action: str,
    *,
    project: Project | None = None,
    task: Task | None = None,
    field: str | None = None,
    old: object = None,
    new: object = None,
    target: str = "",
) -> None:
    """Append one history row. The caller commits, so history and change land together."""
    if task is not None:
        project = project or task.project
        target = target or f"{task.key} {task.title}"
    elif project is not None and not target:
        target = f"{project.key} {project.name}"
    db.add(
        ActivityEvent(
            actor_id=actor.id,
            project_id=project.id if project else None,
            task_id=task.id if task else None,
            action=action,
            field=field,
            old_value=_text(old),
            new_value=_text(new),
            target=target[:255],
        )
    )


def to_out(event: ActivityEvent) -> ActivityOut:
    return ActivityOut(
        id=event.id,
        actor=UserBrief.model_validate(event.actor),
        action=event.action,
        field=event.field,
        old_value=event.old_value,
        new_value=event.new_value,
        target=event.target,
        project_key=event.project.key if event.project else None,
        task_key=event.task.key if event.task else None,
        created_at=event.created_at,
    )

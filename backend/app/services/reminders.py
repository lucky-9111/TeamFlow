"""Due-date reminders, sent by `python -m app.cli send-due-reminders` (run once a day from cron or Task
Scheduler). Nothing runs inside the API process, so several API workers can never start duplicate jobs.

Each (task, due date) is reminded at most once: the TaskReminder row is the lock. Moving the due date
makes the task eligible again for its new date.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.enums import NotificationType, TaskStatus
from app.models.notification import Notification
from app.models.project import Project
from app.models.task import Task, TaskReminder
from app.services.tasks import watchers_to_notify


def _message(task: Task, today: date) -> str:
    when = "today" if task.due_date == today else f"on {task.due_date.isoformat()}"
    if task.due_date == today + timedelta(days=1):
        when = "tomorrow"
    return f"{task.key} is due {when}: {task.title}"


def send_due_reminders(db: Session, today: date, days_ahead: int = 1) -> int:
    """Remind assignees and watchers of open tasks due between today and today + days_ahead.

    Returns the number of tasks reminded. Users who turned off due reminders are skipped.
    """
    already_sent = select(TaskReminder.task_id).where(
        TaskReminder.task_id == Task.id, TaskReminder.due_date == Task.due_date
    )
    tasks = db.scalars(
        select(Task)
        .join(Project, Task.project_id == Project.id)
        .where(
            Task.status != TaskStatus.DONE,
            Task.due_date >= today,
            Task.due_date <= today + timedelta(days=days_ahead),
            Project.archived_at.is_(None),
            ~already_sent.exists(),
        )
        .options(selectinload(Task.project), selectinload(Task.assignee), selectinload(Task.watchers))
        .order_by(Task.id)
    ).all()

    reminded = 0
    for task in tasks:
        recipients = {u.id: u for u in [task.assignee, *watchers_to_notify(db, task)] if u is not None}
        db.add(TaskReminder(task_id=task.id, due_date=task.due_date))
        for user in recipients.values():
            if user.is_active and user.due_reminders:
                db.add(
                    Notification(
                        recipient_id=user.id,
                        type=NotificationType.TASK_DUE,
                        project_id=task.project_id,
                        task_id=task.id,
                        message=_message(task, today)[:255],
                    )
                )
        try:
            db.commit()
            reminded += 1
        except IntegrityError:
            # Another run sent this reminder first; its notifications stand, ours are dropped.
            db.rollback()
    return reminded

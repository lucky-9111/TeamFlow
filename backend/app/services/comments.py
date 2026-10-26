from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFound, PermissionDenied
from app.core.permissions import Action
from app.models.base import utcnow
from app.models.enums import NotificationType
from app.models.task import Task, TaskComment
from app.models.user import User
from app.schemas.tasks import CommentOut
from app.schemas.users import UserBrief
from app.services import activity
from app.services.access import TaskAccess, ensure_not_archived, get_task
from app.services.notifications import notify
from app.services.tasks import watchers_to_notify


def _can_modify(user: User, access: TaskAccess, comment: TaskComment) -> bool:
    if access.project.archived_at is not None:
        return False
    return comment.author_id == user.id or access.can(user, Action.COMMENT_MODERATE)


def _out(user: User, access: TaskAccess, comment: TaskComment) -> CommentOut:
    return CommentOut(
        id=comment.id,
        author=UserBrief.model_validate(comment.author),
        body=comment.body,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
        can_edit=_can_modify(user, access, comment),
    )


def list_comments(db: Session, user: User, access: TaskAccess) -> list[CommentOut]:
    rows = db.scalars(
        select(TaskComment)
        .where(TaskComment.task_id == access.task.id)
        .options(selectinload(TaskComment.author))
        .order_by(TaskComment.created_at, TaskComment.id)
    )
    return [_out(user, access, c) for c in rows]


def add_comment(db: Session, user: User, access: TaskAccess, body: str) -> CommentOut:
    task = access.task
    ensure_not_archived(access.project)
    access.require(user, Action.TASK_COMMENT)
    comment = TaskComment(task_id=task.id, author=user, body=body)
    db.add(comment)
    activity.record(db, user, "comment_added", task=task)
    notify(
        db,
        [task.assignee, task.reporter, *watchers_to_notify(db, task)],
        user,
        NotificationType.TASK_COMMENT,
        f"{user.full_name} commented on {task.key}",
        task=task,
    )
    db.commit()
    return _out(user, access, comment)


def _load(db: Session, user: User, comment_id: int) -> tuple[TaskComment, TaskAccess]:
    comment = db.get(TaskComment, comment_id)
    if comment is None:
        raise NotFound("Comment not found")
    task = db.get(Task, comment.task_id)
    access = get_task(db, user, task.key)  # raises 404 if the user can't see the task
    if not _can_modify(user, access, comment):
        raise PermissionDenied("You can only change your own comments")
    return comment, access


def edit_comment(db: Session, user: User, comment_id: int, body: str) -> CommentOut:
    comment, access = _load(db, user, comment_id)
    comment.body = body
    comment.edited_at = utcnow()
    db.commit()
    return _out(user, access, comment)


def delete_comment(db: Session, user: User, comment_id: int) -> None:
    comment, _ = _load(db, user, comment_id)
    db.delete(comment)
    db.commit()

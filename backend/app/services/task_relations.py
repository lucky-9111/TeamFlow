"""Dependencies, labels and watchers: the links around a task.

Editing dependencies and labels needs the same right as editing the task. Anyone who can see a task
may watch it. Every lookup goes through `get_task`, so another project's tasks stay invisible (404).
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFound, PermissionDenied, ValidationFailed
from app.models.enums import TaskStatus
from app.models.task import Task, TaskDependency, TaskLabel, TaskWatcher
from app.models.user import User
from app.schemas.tasks import (
    BulkFailure,
    BulkResult,
    BulkUpdateRequest,
    TaskDependencies,
    TaskDetail,
    TransitionRequest,
    UpdateTaskRequest,
)
from app.services import activity
from app.services.access import TaskAccess, ensure_not_archived, get_task
from app.services.tasks import _EAGER, _can_edit, detail, to_out, transition, update_task

MAX_LABELS = 10


def _require_edit(user: User, access: TaskAccess) -> None:
    ensure_not_archived(access.project)
    if not _can_edit(user, access, access.task):
        raise PermissionDenied("You can only edit tasks you reported or are assigned to")


# ---------------------------------------------------------------- dependencies


def dependencies(db: Session, user: User, access: TaskAccess) -> TaskDependencies:
    today = activity.today_for(user)
    task = access.task
    prerequisites = db.scalars(
        select(Task)
        .join(TaskDependency, TaskDependency.depends_on_id == Task.id)
        .where(TaskDependency.task_id == task.id)
        .options(*_EAGER)
        .order_by(Task.number)
    ).all()
    blocks = db.scalars(
        select(Task)
        .join(TaskDependency, TaskDependency.task_id == Task.id)
        .where(TaskDependency.depends_on_id == task.id)
        .options(*_EAGER)
        .order_by(Task.number)
    ).all()
    return TaskDependencies(
        depends_on=[to_out(t, today) for t in prerequisites],
        blocks=[to_out(t, today) for t in blocks],
        unfinished=sum(1 for t in prerequisites if t.status != TaskStatus.DONE),
    )


def _reaches(db: Session, start_id: int, target_id: int) -> bool:
    """True if `start` already depends on `target`, directly or through other tasks."""
    seen: set[int] = set()
    frontier = [start_id]
    while frontier:
        if target_id in frontier:
            return True
        seen.update(frontier)
        frontier = [
            i
            for i in db.scalars(
                select(TaskDependency.depends_on_id).where(TaskDependency.task_id.in_(frontier))
            )
            if i not in seen
        ]
    return False


def add_dependency(db: Session, user: User, access: TaskAccess, depends_on_key: str) -> TaskDependencies:
    _require_edit(user, access)
    task = access.task
    try:
        other = get_task(db, user, depends_on_key).task
    except NotFound as exc:
        raise ValidationFailed("Prerequisite task not found", code="invalid_dependency") from exc
    if other.id == task.id:
        raise ValidationFailed("A task cannot depend on itself", code="invalid_dependency")
    if other.project_id != task.project_id:
        raise ValidationFailed("Dependencies must be in the same project", code="invalid_dependency")
    if db.get(TaskDependency, (task.id, other.id)) is None:
        # Adding task -> other closes a loop if other already (indirectly) depends on task.
        if _reaches(db, other.id, task.id):
            raise ValidationFailed(
                f"{other.key} already depends on {task.key}; this would create a cycle",
                code="dependency_cycle",
            )
        db.add(TaskDependency(task_id=task.id, depends_on_id=other.id, created_by_id=user.id))
        activity.record(db, user, "dependency_added", task=task, field="depends_on", new=other.key)
        db.commit()
    return dependencies(db, user, access)


def remove_dependency(db: Session, user: User, access: TaskAccess, depends_on_key: str) -> TaskDependencies:
    _require_edit(user, access)
    other = get_task(db, user, depends_on_key).task
    link = db.get(TaskDependency, (access.task.id, other.id))
    if link is None:
        raise NotFound("Dependency not found")
    db.delete(link)
    activity.record(db, user, "dependency_removed", task=access.task, field="depends_on", old=other.key)
    db.commit()
    return dependencies(db, user, access)


# ---------------------------------------------------------------- labels


def add_label(db: Session, user: User, access: TaskAccess, name: str, *, commit: bool = True) -> None:
    """`name` must already be normalized (LabelRequest). Adding an existing label is a no-op."""
    _require_edit(user, access)
    task = access.task
    if any(label.name == name for label in task.labels):
        return
    if len(task.labels) >= MAX_LABELS:
        raise ValidationFailed(f"A task can have at most {MAX_LABELS} labels", code="too_many_labels")
    task.labels.append(TaskLabel(name=name))
    activity.record(db, user, "label_added", task=task, field="label", new=name)
    if commit:
        db.commit()


def remove_label(db: Session, user: User, access: TaskAccess, name: str) -> None:
    _require_edit(user, access)
    task = access.task
    label = next((label for label in task.labels if label.name == name.lower()), None)
    if label is None:
        raise NotFound("Label not found on this task")
    task.labels.remove(label)
    activity.record(db, user, "label_removed", task=task, field="label", old=label.name)
    db.commit()


def project_labels(db: Session, project_id: int) -> list[str]:
    """Labels already used in the project, for suggestions."""
    return list(
        db.scalars(
            select(TaskLabel.name)
            .join(Task, Task.id == TaskLabel.task_id)
            .where(Task.project_id == project_id)
            .distinct()
            .order_by(TaskLabel.name)
        )
    )


# ---------------------------------------------------------------- watchers


def watch(db: Session, user: User, access: TaskAccess) -> TaskDetail:
    if db.get(TaskWatcher, (access.task.id, user.id)) is None:
        db.add(TaskWatcher(task_id=access.task.id, user_id=user.id))
        db.commit()
        db.refresh(access.task)
    return detail(user, access)


def unwatch(db: Session, user: User, access: TaskAccess) -> TaskDetail:
    db.execute(
        delete(TaskWatcher).where(TaskWatcher.task_id == access.task.id, TaskWatcher.user_id == user.id)
    )
    db.commit()
    db.refresh(access.task)
    return detail(user, access)


# ---------------------------------------------------------------- bulk actions


def bulk_update(db: Session, user: User, body: BulkUpdateRequest) -> BulkResult:
    """Apply one change to each task separately, through the same rules as a single edit.

    Each task is its own transaction, so one failure (no permission, invalid status move, ...) never
    undoes or blocks the others; failures are reported per task instead.
    """
    updated: list[str] = []
    failed: list[BulkFailure] = []
    for key in dict.fromkeys(k.strip().upper() for k in body.task_keys):
        try:
            access = get_task(db, user, key)
            version = access.task.version
            if "assignee_id" in body.model_fields_set:
                update_task(
                    db, user, access, UpdateTaskRequest(version=version, assignee_id=body.assignee_id)
                )
            elif body.priority is not None:
                update_task(db, user, access, UpdateTaskRequest(version=version, priority=body.priority))
            elif body.status is not None:
                transition(db, user, access, TransitionRequest(to_status=body.status, version=version))
            else:
                add_label(db, user, access, body.add_label)
            updated.append(access.task.key)
        except AppError as exc:
            db.rollback()
            failed.append(BulkFailure(key=key, message=exc.message))
    return BulkResult(updated=updated, failed=failed)

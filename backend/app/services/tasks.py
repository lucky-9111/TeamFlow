import re
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Action, can, require
from app.models.base import utcnow
from app.models.enums import STATUS_LABELS, TaskPriority, TaskStatus
from app.models.project import Project, ProjectMember
from app.models.task import Activity, Task, TaskComment
from app.models.user import User
from app.schemas.common import Page
from app.schemas.task import ActivityOut, CommentCreate, TaskCreate, TaskOut, TaskUpdate
from app.schemas.user import ProjectRef, UserBrief
from app.services import activity, projects

TASK_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]{1,9})-(\d{1,9})$")

_PRIORITY_ORDER = {TaskPriority.URGENT: 0, TaskPriority.HIGH: 1, TaskPriority.MEDIUM: 2, TaskPriority.LOW: 3}
_STATUS_ORDER = {TaskStatus.TODO: 0, TaskStatus.IN_PROGRESS: 1, TaskStatus.IN_REVIEW: 2, TaskStatus.DONE: 3}
SORT_FIELDS = ("created_at", "updated_at", "due_date", "priority", "status", "title")

LOAD = (selectinload(Task.project), selectinload(Task.assignee), selectinload(Task.creator))
ACTIVITY_LOAD = (
    selectinload(Activity.actor),
    selectinload(Activity.project),
    selectinload(Activity.task).selectinload(Task.project),
)
_DISPLAY_FIELDS = {
    "title": "title",
    "description": "description",
    "type": "type",
    "priority": "priority",
    "start_date": "start date",
    "due_date": "due date",
}


# ---------------------------------------------------------------- serialization


def member_project_ids(db: Session, user: User) -> set[int]:
    return set(db.scalars(select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)))


def task_out(task: Task, user: User, member_of: set[int]) -> TaskOut:
    member = task.project_id in member_of
    return TaskOut(
        id=task.id,
        key=task.key,
        project=ProjectRef.model_validate(task.project),
        title=task.title,
        description=task.description,
        type=task.type,
        status=task.status,
        priority=task.priority,
        assignee=UserBrief.model_validate(task.assignee) if task.assignee else None,
        creator=UserBrief.model_validate(task.creator),
        start_date=task.start_date,
        due_date=task.due_date,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        can_edit=_can_edit(user, task, member),
        can_delete=can(
            user, Action.TASK_DELETE, is_project_member=member, is_creator=task.creator_id == user.id
        )
        and task.project.archived_at is None,
    )


def _can_edit(user: User, task: Task, member: bool) -> bool:
    return task.project.archived_at is None and can(
        user,
        Action.TASK_EDIT,
        is_project_member=member,
        is_assignee=task.assignee_id == user.id,
        is_creator=task.creator_id == user.id,
    )


def activity_out(entry: Activity) -> ActivityOut:
    return ActivityOut(
        id=entry.id,
        actor=UserBrief.model_validate(entry.actor),
        action=entry.action,
        field=entry.field,
        old_value=entry.old_value,
        new_value=entry.new_value,
        summary=entry.summary,
        task_key=entry.task.key if entry.task else None,
        project_key=entry.project.key,
        created_at=entry.created_at,
    )


# ---------------------------------------------------------------- lookup


def parse_key(raw: str) -> tuple[str, int]:
    match = TASK_KEY_RE.match(raw)
    if not match:
        raise NotFound("Task not found")
    return match.group(1).upper(), int(match.group(2))


@dataclass
class TaskAccess:
    task: Task
    is_member: bool


def get_task(db: Session, user: User, raw_key: str) -> TaskAccess:
    """404 for both missing tasks and tasks in projects the user cannot see."""
    project_key, number = parse_key(raw_key)
    task = db.scalar(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Project.key == project_key, Task.number == number)
        .options(*LOAD)
    )
    if task is None:
        raise NotFound("Task not found")
    member = projects.is_member(db, task.project_id, user.id)
    if not member and not user.is_admin:
        raise NotFound("Task not found")
    return TaskAccess(task, member)


def _ensure_project_writable(project: Project) -> None:
    if project.archived_at is not None:
        raise Conflict("This project is archived and read-only", code="project_archived")


def _validate_assignee(db: Session, project: Project, assignee_id: int | None) -> User | None:
    if assignee_id is None:
        return None
    user = db.get(User, assignee_id)
    if user is None or not user.is_active or not projects.is_member(db, project.id, assignee_id):
        raise ValidationFailed("Assignee must be an active member of the project", code="invalid_assignee")
    return user


def _next_number(db: Session, project_id: int) -> int:
    # Single atomic UPDATE ... RETURNING, so concurrent creates can never share a number.
    return db.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(next_task_number=Project.next_task_number + 1)
        .returning(Project.next_task_number - 1)
    ).scalar_one()


# ---------------------------------------------------------------- commands


def create_task(db: Session, actor: User, project_key: str, data: TaskCreate) -> Task:
    access = projects.get_project(db, actor, project_key)
    project = access.project
    require(actor, Action.TASK_CREATE, is_project_member=access.is_member)
    _ensure_project_writable(project)
    assignee = _validate_assignee(db, project, data.assignee_id)

    task = Task(
        project_id=project.id,
        number=_next_number(db, project.id),
        title=data.title.strip(),
        description=data.description,
        type=data.type,
        status=data.status,
        priority=data.priority,
        assignee_id=assignee.id if assignee else None,
        creator_id=actor.id,
        start_date=data.start_date,
        due_date=data.due_date,
        completed_at=utcnow() if data.status == TaskStatus.DONE else None,
    )
    db.add(task)
    db.flush()
    key = f"{project.key}-{task.number}"
    activity.record(
        db, project_id=project.id, actor=actor, task=task, action="task.created", summary=f"created {key}"
    )
    if assignee:
        activity.notify(
            db,
            recipient_id=assignee.id,
            actor=actor,
            task=task,
            kind="assigned",
            message=f"{actor.full_name} assigned you {key}: {task.title}",
        )
    db.commit()
    return get_task(db, actor, key).task


def update_task(db: Session, actor: User, access: TaskAccess, data: TaskUpdate) -> Task:
    task = access.task
    require(
        actor,
        Action.TASK_EDIT,
        is_project_member=access.is_member,
        is_assignee=task.assignee_id == actor.id,
        is_creator=task.creator_id == actor.id,
    )
    _ensure_project_writable(task.project)
    changes = data.model_dump(exclude_unset=True)
    for field in ("title", "description", "type", "status", "priority"):
        if field in changes and changes[field] is None:
            raise ValidationFailed(f"{field} cannot be null")

    start = changes.get("start_date", task.start_date)
    due = changes.get("due_date", task.due_date)
    if start and due and due < start:
        raise ValidationFailed("due_date must not be before start_date")

    key = task.key
    project_id = task.project_id

    def log(action: str, summary: str, field: str, old, new) -> None:
        activity.record(
            db,
            project_id=project_id,
            actor=actor,
            task=task,
            action=action,
            summary=summary,
            field=field,
            old_value=None if old is None else str(old),
            new_value=None if new is None else str(new),
        )

    if "status" in changes and changes["status"] != task.status:
        old, new = task.status, changes["status"]
        task.status = new
        task.completed_at = utcnow() if new == TaskStatus.DONE else None
        log(
            "task.status_changed",
            f"moved {key} from {STATUS_LABELS[old]} to {STATUS_LABELS[new]}",
            "status",
            old,
            new,
        )
        activity.notify(
            db,
            recipient_id=task.assignee_id,
            actor=actor,
            task=task,
            kind="status",
            message=f"{actor.full_name} moved {key} to {STATUS_LABELS[new]}",
        )

    if "assignee_id" in changes and changes["assignee_id"] != task.assignee_id:
        old_assignee = task.assignee
        assignee = _validate_assignee(db, task.project, changes["assignee_id"])
        task.assignee_id = assignee.id if assignee else None
        task.assignee = assignee
        summary = f"assigned {key} to {assignee.full_name}" if assignee else f"unassigned {key}"
        log(
            "task.assigned",
            summary,
            "assignee",
            old_assignee.full_name if old_assignee else None,
            assignee.full_name if assignee else None,
        )
        if assignee:
            activity.notify(
                db,
                recipient_id=assignee.id,
                actor=actor,
                task=task,
                kind="assigned",
                message=f"{actor.full_name} assigned you {key}: {task.title}",
            )

    for field, label in _DISPLAY_FIELDS.items():
        if field in changes and changes[field] != getattr(task, field):
            old, new = getattr(task, field), changes[field]
            value = changes[field].strip() if field == "title" else changes[field]
            setattr(task, field, value)
            if field == "description":
                old, new = None, None  # keep long text out of the history rows
            log("task.updated", f"changed the {label} of {key}", field, old, new)

    db.commit()
    return get_task(db, actor, key).task


def delete_task(db: Session, actor: User, access: TaskAccess) -> None:
    task = access.task
    require(
        actor, Action.TASK_DELETE, is_project_member=access.is_member, is_creator=task.creator_id == actor.id
    )
    _ensure_project_writable(task.project)
    activity.record(
        db,
        project_id=task.project_id,
        actor=actor,
        action="task.deleted",
        summary=f"deleted {task.key}: {task.title}",
    )
    db.delete(task)
    db.commit()


def add_comment(db: Session, actor: User, access: TaskAccess, data: CommentCreate) -> TaskComment:
    task = access.task
    require(actor, Action.TASK_COMMENT, is_project_member=access.is_member)
    comment = TaskComment(task_id=task.id, author_id=actor.id, body=data.body.strip())
    db.add(comment)
    activity.record(
        db,
        project_id=task.project_id,
        actor=actor,
        task=task,
        action="task.commented",
        summary=f"commented on {task.key}",
    )
    for recipient in {task.assignee_id, task.creator_id}:
        activity.notify(
            db,
            recipient_id=recipient,
            actor=actor,
            task=task,
            kind="comment",
            message=f"{actor.full_name} commented on {task.key}",
        )
    db.commit()
    db.refresh(comment)
    return comment


def list_comments(db: Session, task: Task) -> list[TaskComment]:
    return list(
        db.scalars(
            select(TaskComment)
            .where(TaskComment.task_id == task.id)
            .options(selectinload(TaskComment.author))
            .order_by(TaskComment.created_at, TaskComment.id)
        )
    )


def list_task_activity(db: Session, task: Task) -> list[ActivityOut]:
    rows = db.scalars(
        select(Activity)
        .where(Activity.task_id == task.id)
        .options(*ACTIVITY_LOAD)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
    )
    return [activity_out(row) for row in rows]


# ---------------------------------------------------------------- queries


def _visible(stmt, db: Session, user: User):
    visible = projects.accessible_project_ids(db, user)
    return stmt if visible is None else stmt.where(Task.project_id.in_(visible))


def list_tasks(
    db: Session,
    user: User,
    *,
    project: str | None = None,
    status: list[TaskStatus] | None = None,
    priority: list[TaskPriority] | None = None,
    assignee: str | None = None,
    q: str | None = None,
    overdue: bool = False,
    due_before: date | None = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 25,
    include_archived: bool = False,
) -> Page[TaskOut]:
    stmt = _visible(select(Task).join(Project, Project.id == Task.project_id), db, user)
    if not include_archived:
        stmt = stmt.where(Project.archived_at.is_(None))
    if project:
        stmt = stmt.where(Project.key == project.upper())
    if status:
        stmt = stmt.where(Task.status.in_(status))
    if priority:
        stmt = stmt.where(Task.priority.in_(priority))
    if assignee == "me":
        stmt = stmt.where(Task.assignee_id == user.id)
    elif assignee == "none":
        stmt = stmt.where(Task.assignee_id.is_(None))
    elif assignee:
        if not assignee.isdigit():
            raise ValidationFailed("assignee must be 'me', 'none' or a user id")
        stmt = stmt.where(Task.assignee_id == int(assignee))
    if q and q.strip():
        term = q.strip()
        like = f"%{term}%"
        clauses = [Task.title.ilike(like)]
        match = TASK_KEY_RE.match(term)
        if match:
            clauses.append((Project.key == match.group(1).upper()) & (Task.number == int(match.group(2))))
        stmt = stmt.where(or_(*clauses))
    if overdue:
        stmt = stmt.where(Task.due_date < projects.today(), Task.status != TaskStatus.DONE)
    if due_before:
        stmt = stmt.where(Task.due_date <= due_before)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))

    if sort not in SORT_FIELDS:
        raise ValidationFailed(f"sort must be one of {', '.join(SORT_FIELDS)}")
    if sort == "priority":
        column = case(_PRIORITY_ORDER, value=Task.priority)
    elif sort == "status":
        column = case(_STATUS_ORDER, value=Task.status)
    else:
        column = getattr(Task, sort)
    ordered = column.asc() if order == "asc" else column.desc()
    if sort == "due_date":
        ordered = ordered.nulls_last()
    stmt = (
        stmt.order_by(ordered, Task.id.desc()).options(*LOAD).limit(page_size).offset((page - 1) * page_size)
    )

    member_of = member_project_ids(db, user)
    items = [task_out(t, user, member_of) for t in db.scalars(stmt)]
    return Page[TaskOut](items=items, total=total, page=page, page_size=page_size)


def search(db: Session, user: User, q: str) -> tuple[list[TaskOut], list[Project]]:
    tasks = list_tasks(db, user, q=q, page_size=8, include_archived=True).items
    found = projects.list_projects(db, user, include_archived=False, q=q)[:5]
    return tasks, found


def week_ahead() -> date:
    return projects.today() + timedelta(days=7)

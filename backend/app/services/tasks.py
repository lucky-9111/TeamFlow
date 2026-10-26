from datetime import date

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import AppError, Conflict, PermissionDenied, ValidationFailed
from app.core.permissions import Action
from app.models.base import utcnow
from app.models.enums import PRIORITY_RANK, NotificationType, TaskPriority, TaskStatus, TaskType
from app.models.project import Project
from app.models.task import Task, TaskLabel
from app.models.user import User
from app.schemas.common import Page
from app.schemas.projects import TaskCounts
from app.schemas.tasks import (
    Board,
    BoardColumn,
    CreateTaskRequest,
    ProjectRef,
    SubtaskList,
    TaskDetail,
    TaskOut,
    TaskPermissions,
    TaskSort,
    TransitionRequest,
    UpdateTaskRequest,
)
from app.schemas.users import UserBrief
from app.services import activity, workflow
from app.services.access import (
    ProjectAccess,
    TaskAccess,
    accessible_project_ids,
    ensure_not_archived,
    member_role,
)
from app.services.notifications import notify

MAX_PAGE_SIZE = 100
BOARD_LIMIT = 500

_STATUS_ORDER = {s: i for i, s in enumerate(TaskStatus)}
_EAGER = (
    selectinload(Task.project),
    selectinload(Task.assignee),
    selectinload(Task.reporter),
    selectinload(Task.parent),
    selectinload(Task.labels),
)


class InvalidTransition(AppError):
    code = "invalid_transition"


# ---------------------------------------------------------------- serialization


def is_overdue(task: Task, today: date) -> bool:
    return task.due_date is not None and task.due_date < today and task.status != TaskStatus.DONE


def to_out(task: Task, today: date, transitions: list[TaskStatus] | None = None) -> TaskOut:
    return TaskOut(
        id=task.id,
        key=task.key,
        number=task.number,
        project=ProjectRef(id=task.project.id, key=task.project.key, name=task.project.name),
        type=task.type,
        status=task.status,
        priority=task.priority,
        title=task.title,
        description=task.description,
        reporter=UserBrief.model_validate(task.reporter),
        assignee=UserBrief.model_validate(task.assignee) if task.assignee else None,
        parent_key=f"{task.project.key}-{task.parent.number}" if task.parent else None,
        labels=[label.name for label in task.labels],
        start_date=task.start_date,
        due_date=task.due_date,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        version=task.version,
        is_overdue=is_overdue(task, today),
        allowed_transitions=transitions or [],
    )


def _can_edit(user: User, access: ProjectAccess, task: Task) -> bool:
    if access.project.archived_at is not None or not access.can(user, Action.PROJECT_VIEW):
        return False
    return access.can(user, Action.TASK_EDIT_ANY) or user.id in (task.assignee_id, task.reporter_id)


def permissions(user: User, access: ProjectAccess, task: Task) -> TaskPermissions:
    archived = access.project.archived_at is not None
    can_edit = _can_edit(user, access, task)
    return TaskPermissions(
        can_edit=can_edit,
        can_assign=can_edit,
        can_delete=not archived and access.can(user, Action.TASK_DELETE),
        can_comment=not archived and access.can(user, Action.TASK_COMMENT),
    )


def detail(user: User, access: TaskAccess) -> TaskDetail:
    task = access.task
    out = to_out(task, activity.today_for(user), workflow.allowed_transitions(user, access, task))
    watchers = [w.user for w in task.watchers]
    return TaskDetail(
        **out.model_dump(),
        permissions=permissions(user, access, task),
        watchers=[UserBrief.model_validate(u) for u in watchers],
        watching=any(u.id == user.id for u in watchers),
    )


def watchers_to_notify(db: Session, task: Task) -> list[User]:
    """Watchers who can still see the task: members of its project, or admins."""
    return [
        w.user
        for w in task.watchers
        if w.user.is_admin or member_role(db, task.project_id, w.user_id) is not None
    ]


# ---------------------------------------------------------------- helpers


def _assignee(db: Session, project: Project, assignee_id: int | None) -> User | None:
    if assignee_id is None:
        return None
    user = db.get(User, assignee_id)
    if user is None or not user.is_active or member_role(db, project.id, user.id) is None:
        raise ValidationFailed(
            "The assignee must be an active member of this project", code="invalid_assignee"
        )
    return user


def _check_version(task: Task, version: int) -> None:
    if task.version != version:
        raise Conflict(
            "This task was changed by someone else. Reload it and try again.", code="stale_version"
        )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise Conflict(
            "This task was changed by someone else. Reload it and try again.", code="stale_version"
        ) from exc


def task_counts(db: Session, project_ids: list[int], today: date) -> dict[int, TaskCounts]:
    counts = {pid: TaskCounts() for pid in project_ids}
    if not project_ids:
        return counts
    rows = db.execute(
        select(Task.project_id, Task.status, func.count())
        .where(Task.project_id.in_(project_ids))
        .group_by(Task.project_id, Task.status)
    )
    for pid, status, n in rows:
        setattr(counts[pid], status.value, n)
        counts[pid].total += n
    overdue = db.execute(
        select(Task.project_id, func.count())
        .where(Task.project_id.in_(project_ids), Task.due_date < today, Task.status != TaskStatus.DONE)
        .group_by(Task.project_id)
    )
    for pid, n in overdue:
        counts[pid].overdue = n
    return counts


# ---------------------------------------------------------------- commands


def create_task(
    db: Session, user: User, access: ProjectAccess, body: CreateTaskRequest, parent: Task | None = None
) -> TaskDetail:
    project = access.project
    ensure_not_archived(project)
    access.require(user, Action.TASK_CREATE)
    if not project.members_can_create_tasks and not access.can(user, Action.TASK_EDIT_ANY):
        raise PermissionDenied("Only project managers can create tasks in this project")
    # One level only: a subtask cannot have subtasks, so parent/child loops are impossible.
    if parent is not None and parent.parent_id is not None:
        raise ValidationFailed("A subtask cannot have its own subtasks", code="nested_subtask")
    assignee = _assignee(db, project, body.assignee_id)

    # Atomic counter: concurrent creates can never get the same number (UNIQUE is the backstop).
    number = (
        db.execute(
            update(Project)
            .where(Project.id == project.id)
            .values(next_task_number=Project.next_task_number + 1)
            .returning(Project.next_task_number)
            .execution_options(synchronize_session=False)
        ).scalar_one()
        - 1
    )

    task = Task(
        project=project,
        number=number,
        type=body.type,
        priority=body.priority,
        title=body.title,
        description=body.description,
        reporter=user,
        assignee=assignee,
        start_date=body.start_date,
        due_date=body.due_date,
        parent=parent,
    )
    db.add(task)
    db.flush()
    activity.record(db, user, "task_created", task=task)
    if assignee:
        notify(
            db,
            [assignee],
            user,
            NotificationType.TASK_ASSIGNED,
            f"{user.full_name} assigned {task.key} to you",
            task=task,
        )
    db.commit()
    db.refresh(task)
    return detail(user, TaskAccess(project=project, role=access.role, task=task))


def update_task(db: Session, user: User, access: TaskAccess, body: UpdateTaskRequest) -> TaskDetail:
    task = access.task
    ensure_not_archived(access.project)
    if not _can_edit(user, access, task):
        raise PermissionDenied("You can only edit tasks you reported or are assigned to")
    _check_version(task, body.version)

    changes = body.model_dump(exclude_unset=True, exclude={"version"})
    start = changes.get("start_date", task.start_date)
    due = changes.get("due_date", task.due_date)
    if start and due and due < start:
        raise ValidationFailed("Due date cannot be before the start date")

    for field in ("title", "description", "type", "priority", "start_date", "due_date"):
        if field not in changes or changes[field] == getattr(task, field):
            continue
        if field in ("title", "type", "priority") and changes[field] is None:
            raise ValidationFailed(f"{field} cannot be empty")
        old = getattr(task, field)
        setattr(task, field, changes[field] if field != "description" else (changes[field] or ""))
        if field == "description":
            activity.record(db, user, "task_updated", task=task, field=field)
        else:
            activity.record(db, user, "task_updated", task=task, field=field, old=old, new=changes[field])

    if "assignee_id" in changes and changes["assignee_id"] != task.assignee_id:
        new_assignee = _assignee(db, access.project, changes["assignee_id"])
        old_name = task.assignee.full_name if task.assignee else None
        task.assignee = new_assignee
        activity.record(
            db,
            user,
            "task_assigned",
            task=task,
            field="assignee",
            old=old_name,
            new=new_assignee.full_name if new_assignee else None,
        )
        if new_assignee:
            notify(
                db,
                [new_assignee],
                user,
                NotificationType.TASK_ASSIGNED,
                f"{user.full_name} assigned {task.key} to you",
                task=task,
            )

    _commit(db)
    db.refresh(task)
    return detail(user, access)


def transition(db: Session, user: User, access: TaskAccess, body: TransitionRequest) -> TaskDetail:
    task = access.task
    ensure_not_archived(access.project)
    _check_version(task, body.version)
    old = task.status
    if old == body.to_status:
        return detail(user, access)
    if not workflow.is_valid(old, body.to_status):
        allowed = ", ".join(workflow.LABELS[s] for s in workflow.TRANSITIONS[old])
        raise InvalidTransition(
            f"A task in {workflow.LABELS[old]} can only move to: {allowed}",
            details={"from": old, "to": body.to_status},
        )
    if not workflow.may_move(user, access, task, body.to_status):
        raise PermissionDenied(
            f"You don't have permission to move this task to {workflow.LABELS[body.to_status]}"
        )

    task.status = body.to_status
    task.completed_at = utcnow() if body.to_status == TaskStatus.DONE else None
    activity.record(db, user, "status_changed", task=task, field="status", old=old, new=body.to_status)
    notify(
        db,
        [task.assignee, task.reporter, *watchers_to_notify(db, task)],
        user,
        NotificationType.TASK_STATUS,
        f"{user.full_name} moved {task.key} to {workflow.LABELS[body.to_status]}",
        task=task,
    )
    _commit(db)
    db.refresh(task)
    return detail(user, access)


def delete_task(db: Session, user: User, access: TaskAccess) -> None:
    task = access.task
    ensure_not_archived(access.project)
    access.require(user, Action.TASK_DELETE)
    if db.scalar(select(func.count()).where(Task.parent_id == task.id)):
        raise Conflict("Delete this task's subtasks first", code="has_subtasks")
    # Project-level event (task_id None) so the deletion stays in the feed after the task is gone.
    activity.record(db, user, "task_deleted", project=access.project, target=f"{task.key} {task.title}")
    db.delete(task)
    db.commit()


# ---------------------------------------------------------------- queries


def _filtered(
    stmt,
    user: User,
    today: date,
    *,
    status: list[TaskStatus] | None = None,
    priority: list[TaskPriority] | None = None,
    type_: list[TaskType] | None = None,
    assignee: str | None = None,
    q: str | None = None,
    overdue: bool | None = None,
    label: str | None = None,
):
    if status:
        stmt = stmt.where(Task.status.in_(status))
    if priority:
        stmt = stmt.where(Task.priority.in_(priority))
    if type_:
        stmt = stmt.where(Task.type.in_(type_))
    if assignee == "me":
        stmt = stmt.where(Task.assignee_id == user.id)
    elif assignee == "none":
        stmt = stmt.where(Task.assignee_id.is_(None))
    elif assignee:
        if not assignee.isdigit():
            raise ValidationFailed("assignee must be a user id, 'me' or 'none'")
        stmt = stmt.where(Task.assignee_id == int(assignee))
    if q:
        q = q.strip()
        parts = q.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            stmt = stmt.where(
                (Task.title.icontains(q, autoescape=True))
                | ((Project.key == parts[0].upper()) & (Task.number == int(parts[1])))
            )
        else:
            stmt = stmt.where(Task.title.icontains(q, autoescape=True))
    if overdue:
        stmt = stmt.where(Task.due_date < today, Task.status != TaskStatus.DONE)
    if label:
        stmt = stmt.where(Task.labels.any(TaskLabel.name == label.strip().lower()))
    return stmt


def _sorted(stmt, sort: TaskSort, descending: bool):
    priority_rank = case(PRIORITY_RANK, value=Task.priority)
    status_rank = case(_STATUS_ORDER, value=Task.status)
    column = {
        "created": Task.created_at,
        "updated": Task.updated_at,
        "due": Task.due_date,
        "priority": priority_rank,
        "status": status_rank,
        "key": Task.number,
    }[sort]
    primary = column.desc() if descending else column.asc()
    if sort == "due":
        # Tasks without a due date always go last.
        return stmt.order_by(Task.due_date.is_(None), primary, Task.id.desc())
    return stmt.order_by(primary, Task.id.desc())


def list_tasks(
    db: Session,
    user: User,
    *,
    project: str | None,
    sort: TaskSort,
    descending: bool,
    page: int,
    page_size: int,
    **filters,
) -> Page[TaskOut]:
    today = activity.today_for(user)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    stmt = (
        select(Task)
        .join(Project, Task.project_id == Project.id)
        .where(Task.project_id.in_(accessible_project_ids(user)))
    )
    if project:
        stmt = stmt.where(Project.key == project.upper())
    else:
        stmt = stmt.where(Project.archived_at.is_(None))
    stmt = _filtered(stmt, user, today, **filters)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(
        _sorted(stmt, sort, descending).options(*_EAGER).offset((page - 1) * page_size).limit(page_size)
    )
    return Page(items=[to_out(t, today) for t in rows], total=total, page=page, page_size=page_size)


def list_subtasks(db: Session, user: User, access: TaskAccess) -> SubtaskList:
    today = activity.today_for(user)
    rows = db.scalars(
        select(Task).where(Task.parent_id == access.task.id).options(*_EAGER).order_by(Task.number)
    )
    items = [to_out(t, today) for t in rows]
    done = sum(1 for t in items if t.status == TaskStatus.DONE)
    return SubtaskList(items=items, done=done, total=len(items))


def board(db: Session, user: User, access: ProjectAccess, **filters) -> Board:
    today = activity.today_for(user)
    stmt = (
        select(Task).join(Project, Task.project_id == Project.id).where(Task.project_id == access.project.id)
    )
    stmt = _filtered(stmt, user, today, **filters)
    priority_rank = case(PRIORITY_RANK, value=Task.priority)
    rows = db.scalars(
        stmt.options(*_EAGER).order_by(priority_rank.desc(), Task.updated_at.desc()).limit(BOARD_LIMIT)
    )

    columns = {s: BoardColumn(status=s, tasks=[]) for s in TaskStatus}
    for task in rows:
        columns[task.status].tasks.append(
            to_out(task, today, workflow.allowed_transitions(user, access, task))
        )
    project = access.project
    return Board(
        project=ProjectRef(id=project.id, key=project.key, name=project.name), columns=list(columns.values())
    )


def open_task_counts(db: Session, user_ids: list[int], project_id: int | None = None) -> dict[int, int]:
    if not user_ids:
        return {}
    stmt = (
        select(Task.assignee_id, func.count())
        .join(Project, Task.project_id == Project.id)
        .where(Task.assignee_id.in_(user_ids), Task.status != TaskStatus.DONE, Project.archived_at.is_(None))
        .group_by(Task.assignee_id)
    )
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    return dict(db.execute(stmt).all())


def unassign_open_tasks(db: Session, actor: User, project: Project, user_id: int) -> None:
    """Called when someone leaves a project: their open tasks go back to the unassigned pool."""
    tasks = db.scalars(
        select(Task).where(
            Task.project_id == project.id, Task.assignee_id == user_id, Task.status != TaskStatus.DONE
        )
    )
    for task in tasks:
        old = task.assignee.full_name if task.assignee else None
        task.assignee = None
        activity.record(db, actor, "task_assigned", task=task, field="assignee", old=old, new=None)

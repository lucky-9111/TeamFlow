from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DB, CurrentUser
from app.models.enums import TaskPriority, TaskStatus
from app.schemas.common import Page
from app.schemas.task import ActivityOut, CommentCreate, CommentOut, TaskOut, TaskUpdate
from app.services import tasks as svc

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _out(db, user, task) -> TaskOut:
    return svc.task_out(task, user, svc.member_project_ids(db, user))


@router.get("", response_model=Page[TaskOut])
def list_tasks(
    db: DB,
    user: CurrentUser,
    project: Annotated[str | None, Query(max_length=10)] = None,
    status_: Annotated[list[TaskStatus] | None, Query(alias="status")] = None,
    priority: Annotated[list[TaskPriority] | None, Query()] = None,
    assignee: Annotated[str | None, Query(max_length=20)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    overdue: bool = False,
    due_before: date | None = None,
    sort: str = "created_at",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    return svc.list_tasks(
        db,
        user,
        project=project,
        status=status_,
        priority=priority,
        assignee=assignee,
        q=q,
        overdue=overdue,
        due_before=due_before,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get("/{key}", response_model=TaskOut)
def get_task(key: str, db: DB, user: CurrentUser):
    return _out(db, user, svc.get_task(db, user, key).task)


@router.patch("/{key}", response_model=TaskOut)
def update_task(key: str, body: TaskUpdate, db: DB, user: CurrentUser):
    task = svc.update_task(db, user, svc.get_task(db, user, key), body)
    return _out(db, user, task)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(key: str, db: DB, user: CurrentUser) -> Response:
    svc.delete_task(db, user, svc.get_task(db, user, key))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{key}/comments", response_model=list[CommentOut])
def list_comments(key: str, db: DB, user: CurrentUser):
    return svc.list_comments(db, svc.get_task(db, user, key).task)


@router.post("/{key}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(key: str, body: CommentCreate, db: DB, user: CurrentUser):
    return svc.add_comment(db, user, svc.get_task(db, user, key), body)


@router.get("/{key}/activity", response_model=list[ActivityOut])
def task_activity(key: str, db: DB, user: CurrentUser):
    return svc.list_task_activity(db, svc.get_task(db, user, key).task)

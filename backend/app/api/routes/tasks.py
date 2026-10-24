from typing import Literal

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DB, CurrentUser
from app.models.enums import TaskPriority, TaskStatus, TaskType
from app.schemas.common import Page
from app.schemas.tasks import (
    ActivityOut,
    CommentOut,
    CommentRequest,
    TaskDetail,
    TaskOut,
    TaskSort,
    TransitionRequest,
    UpdateTaskRequest,
)
from app.services import comments as comment_service
from app.services import dashboard as dashboard_service
from app.services import tasks as task_service
from app.services.access import get_task

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=Page[TaskOut])
def list_tasks(
    user: CurrentUser,
    db: DB,
    project: str | None = None,
    status_: list[TaskStatus] | None = Query(default=None, alias="status"),
    priority: list[TaskPriority] | None = Query(default=None),
    type: list[TaskType] | None = Query(default=None),
    assignee: str | None = Query(default=None, description="user id, 'me' or 'none'"),
    q: str | None = Query(default=None, max_length=200),
    overdue: bool | None = None,
    sort: TaskSort = "updated",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> Page[TaskOut]:
    return task_service.list_tasks(
        db,
        user,
        project=project,
        sort=sort,
        descending=order == "desc",
        page=page,
        page_size=page_size,
        status=status_,
        priority=priority,
        type_=type,
        assignee=assignee,
        q=q,
        overdue=overdue,
    )


@router.get("/tasks/{task_key}", response_model=TaskDetail)
def get_task_detail(task_key: str, user: CurrentUser, db: DB) -> TaskDetail:
    return task_service.detail(user, get_task(db, user, task_key))


@router.patch("/tasks/{task_key}", response_model=TaskDetail)
def update_task(task_key: str, body: UpdateTaskRequest, user: CurrentUser, db: DB) -> TaskDetail:
    return task_service.update_task(db, user, get_task(db, user, task_key), body)


@router.post("/tasks/{task_key}/transitions", response_model=TaskDetail)
def transition_task(task_key: str, body: TransitionRequest, user: CurrentUser, db: DB) -> TaskDetail:
    return task_service.transition(db, user, get_task(db, user, task_key), body)


@router.delete("/tasks/{task_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_key: str, user: CurrentUser, db: DB) -> Response:
    task_service.delete_task(db, user, get_task(db, user, task_key))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks/{task_key}/activity", response_model=list[ActivityOut])
def task_activity(task_key: str, user: CurrentUser, db: DB) -> list[ActivityOut]:
    return dashboard_service.task_history(db, get_task(db, user, task_key).task)


@router.get("/tasks/{task_key}/comments", response_model=list[CommentOut])
def list_comments(task_key: str, user: CurrentUser, db: DB) -> list[CommentOut]:
    return comment_service.list_comments(db, user, get_task(db, user, task_key))


@router.post("/tasks/{task_key}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(task_key: str, body: CommentRequest, user: CurrentUser, db: DB) -> CommentOut:
    return comment_service.add_comment(db, user, get_task(db, user, task_key), body.body)


@router.patch("/comments/{comment_id}", response_model=CommentOut)
def edit_comment(comment_id: int, body: CommentRequest, user: CurrentUser, db: DB) -> CommentOut:
    return comment_service.edit_comment(db, user, comment_id, body.body)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, user: CurrentUser, db: DB) -> Response:
    comment_service.delete_comment(db, user, comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

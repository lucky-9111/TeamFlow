from datetime import date, datetime
from typing import Literal

from pydantic import Field, model_validator

from app.models.enums import TaskPriority, TaskStatus, TaskType
from app.schemas.common import APIModel
from app.schemas.users import UserBrief


class ProjectRef(APIModel):
    id: int
    key: str
    name: str


class TaskOut(APIModel):
    id: int
    key: str
    number: int
    project: ProjectRef
    type: TaskType
    status: TaskStatus
    priority: TaskPriority
    title: str
    description: str
    reporter: UserBrief
    assignee: UserBrief | None
    start_date: date | None
    due_date: date | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int
    is_overdue: bool
    allowed_transitions: list[TaskStatus] = []


class TaskPermissions(APIModel):
    can_edit: bool
    can_assign: bool
    can_delete: bool
    can_comment: bool


class TaskDetail(TaskOut):
    permissions: TaskPermissions


class CreateTaskRequest(APIModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    type: TaskType = TaskType.TASK
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: int | None = None
    start_date: date | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def _dates(self) -> "CreateTaskRequest":
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("Due date cannot be before the start date")
        return self


class UpdateTaskRequest(APIModel):
    """Only fields that are sent are changed. Status changes go through /transitions."""

    version: int
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    type: TaskType | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = None
    start_date: date | None = None
    due_date: date | None = None


class TransitionRequest(APIModel):
    to_status: TaskStatus
    version: int


TaskSort = Literal["created", "updated", "due", "priority", "status", "key"]


class BoardColumn(APIModel):
    status: TaskStatus
    tasks: list[TaskOut]


class Board(APIModel):
    project: ProjectRef
    columns: list[BoardColumn]


class CommentOut(APIModel):
    id: int
    author: UserBrief
    body: str
    created_at: datetime
    edited_at: datetime | None
    can_edit: bool


class CommentRequest(APIModel):
    body: str = Field(min_length=1, max_length=10000)


class ActivityOut(APIModel):
    id: int
    actor: UserBrief
    action: str
    field: str | None
    old_value: str | None
    new_value: str | None
    target: str
    project_key: str | None
    task_key: str | None
    created_at: datetime

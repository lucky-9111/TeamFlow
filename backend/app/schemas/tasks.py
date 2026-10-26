import re
from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

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
    parent_key: str | None = None
    labels: list[str] = []
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
    watchers: list[UserBrief] = []
    watching: bool = False


class SubtaskList(APIModel):
    items: list[TaskOut]
    done: int
    total: int


class DependencyRequest(APIModel):
    depends_on: str = Field(min_length=1, max_length=30, description="key of the prerequisite task")


class TaskDependencies(APIModel):
    depends_on: list[TaskOut]
    blocks: list[TaskOut]
    unfinished: int = Field(description="prerequisites that are not Done yet")


_LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9 _-]*$")


def normalize_label(value: str) -> str:
    """Lower-case, single spaces; letters, digits, spaces, '-' and '_' only."""
    name = " ".join(value.split()).lower()
    if not name or len(name) > 30 or not _LABEL_RE.match(name):
        raise ValueError("Labels are 1-30 characters: letters, numbers, spaces, '-' and '_'")
    return name


class LabelRequest(APIModel):
    name: str

    @field_validator("name")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return normalize_label(v)


BULK_LIMIT = 100


class BulkUpdateRequest(APIModel):
    """Exactly one change per request, applied to every selected task."""

    task_keys: list[str] = Field(min_length=1, max_length=BULK_LIMIT)
    assignee_id: int | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    add_label: str | None = None

    @field_validator("add_label")
    @classmethod
    def _label(cls, v: str | None) -> str | None:
        return None if v is None else normalize_label(v)

    @model_validator(mode="after")
    def _one_change(self) -> "BulkUpdateRequest":
        changes = self.model_fields_set - {"task_keys"}
        if len(changes) != 1:
            raise ValueError("Send exactly one of assignee_id, priority, status or add_label")
        if changes != {"assignee_id"} and getattr(self, changes.pop()) is None:
            raise ValueError("The new value cannot be empty")
        return self


class BulkFailure(APIModel):
    key: str
    message: str


class BulkResult(APIModel):
    updated: list[str]
    failed: list[BulkFailure]


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

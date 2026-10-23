from datetime import date, datetime

from pydantic import Field, model_validator

from app.models.enums import TaskPriority, TaskStatus, TaskType
from app.schemas.common import APIModel, ORMModel
from app.schemas.user import ProjectRef, UserBrief


class TaskCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    type: TaskType = TaskType.TASK
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: int | None = None
    start_date: date | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def _dates_in_order(self):
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("due_date must not be before start_date")
        return self


class TaskUpdate(APIModel):
    """Only fields present in the request are changed, so `assignee_id: null` unassigns."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    type: TaskType | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = None
    start_date: date | None = None
    due_date: date | None = None


class TaskOut(ORMModel):
    id: int
    key: str
    project: ProjectRef
    title: str
    description: str
    type: TaskType
    status: TaskStatus
    priority: TaskPriority
    assignee: UserBrief | None
    creator: UserBrief
    start_date: date | None
    due_date: date | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    can_delete: bool


class CommentCreate(APIModel):
    body: str = Field(min_length=1, max_length=10000)


class CommentOut(ORMModel):
    id: int
    author: UserBrief
    body: str
    created_at: datetime


class ActivityOut(ORMModel):
    id: int
    actor: UserBrief
    action: str
    field: str | None
    old_value: str | None
    new_value: str | None
    summary: str
    task_key: str | None = None
    project_key: str
    created_at: datetime


class NotificationOut(ORMModel):
    id: int
    kind: str
    message: str
    task_key: str | None = None
    read: bool
    created_at: datetime


class NotificationList(ORMModel):
    items: list[NotificationOut]
    unread_count: int


class DashboardOut(ORMModel):
    active_projects: int
    open_tasks: int
    my_open_tasks: int
    overdue_tasks: int
    completed_recently: int
    upcoming_deadlines: list[TaskOut]
    my_tasks: list[TaskOut]
    recent_activity: list[ActivityOut]


class SearchResults(ORMModel):
    tasks: list[TaskOut]
    projects: list[ProjectRef]

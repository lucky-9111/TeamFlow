from datetime import datetime

from app.models.enums import NotificationType
from app.schemas.common import APIModel
from app.schemas.tasks import ActivityOut, TaskOut


class DashboardStats(APIModel):
    active_projects: int
    open_tasks: int
    my_open_tasks: int
    overdue_tasks: int
    completed_last_7_days: int


class ProjectProgress(APIModel):
    key: str
    name: str
    done: int
    total: int


class Dashboard(APIModel):
    stats: DashboardStats
    my_tasks: list[TaskOut]
    upcoming: list[TaskOut]
    recently_completed: list[TaskOut]
    recent_activity: list[ActivityOut]
    projects: list[ProjectProgress]


class SearchProject(APIModel):
    key: str
    name: str


class SearchResults(APIModel):
    projects: list[SearchProject]
    tasks: list[TaskOut]


class NotificationOut(APIModel):
    id: int
    type: NotificationType
    message: str
    actor_name: str | None
    project_key: str | None
    task_key: str | None
    read: bool
    created_at: datetime


class UnreadCount(APIModel):
    count: int

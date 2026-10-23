from datetime import date, datetime

from pydantic import Field, model_validator

from app.models.enums import ProjectRole, ProjectStatus
from app.schemas.common import APIModel, ORMModel
from app.schemas.users import UserBrief

PROJECT_KEY_PATTERN = r"^[A-Z][A-Z0-9]{1,9}$"


def _check_dates(start: date | None, end: date | None) -> None:
    if start and end and end < start:
        raise ValueError("End date cannot be before the start date")


class CreateProjectRequest(APIModel):
    key: str = Field(pattern=PROJECT_KEY_PATTERN, description="2-10 uppercase letters/digits, e.g. TF")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=5000)
    status: ProjectStatus = ProjectStatus.ACTIVE
    start_date: date | None = None
    end_date: date | None = None
    members_can_create_tasks: bool = True

    @model_validator(mode="after")
    def _dates(self) -> "CreateProjectRequest":
        _check_dates(self.start_date, self.end_date)
        return self


class UpdateProjectRequest(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    members_can_create_tasks: bool | None = None


class ProjectMemberOut(APIModel):
    user: UserBrief
    role: ProjectRole
    is_active: bool
    open_task_count: int
    added_at: datetime


class AddMemberRequest(APIModel):
    user_id: int
    role: ProjectRole = ProjectRole.DEVELOPER


class UpdateMemberRequest(APIModel):
    role: ProjectRole


class TaskCounts(APIModel):
    todo: int = 0
    in_progress: int = 0
    in_review: int = 0
    done: int = 0
    total: int = 0
    overdue: int = 0


class ProjectPermissions(APIModel):
    can_edit: bool
    can_manage_members: bool
    can_archive: bool
    can_create_task: bool


class ProjectOut(ORMModel):
    id: int
    key: str
    name: str
    description: str
    status: ProjectStatus
    start_date: date | None
    end_date: date | None
    archived_at: datetime | None
    members_can_create_tasks: bool
    created_at: datetime
    owner: UserBrief
    my_role: ProjectRole | None = None
    member_count: int = 0
    counts: TaskCounts = TaskCounts()


class ProjectDetail(ProjectOut):
    members: list[ProjectMemberOut]
    permissions: ProjectPermissions

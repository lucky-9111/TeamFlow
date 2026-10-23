from datetime import date, datetime

from pydantic import Field, model_validator

from app.models.enums import ProjectStatus
from app.schemas.common import APIModel, ORMModel
from app.schemas.user import UserBrief


class ProjectCreate(APIModel):
    key: str = Field(min_length=2, max_length=10)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=5000)
    status: ProjectStatus = ProjectStatus.ACTIVE
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _dates_in_order(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class ProjectUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None


class MemberAdd(APIModel):
    user_id: int


class ProjectOut(ORMModel):
    id: int
    key: str
    name: str
    description: str
    status: ProjectStatus
    start_date: date | None
    end_date: date | None
    owner: UserBrief
    is_archived: bool
    task_count: int
    done_count: int
    member_count: int
    created_at: datetime


class ProjectDetail(ProjectOut):
    members: list[UserBrief]
    can_manage: bool

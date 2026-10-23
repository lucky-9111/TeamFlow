from datetime import datetime

from pydantic import EmailStr, Field

from app.core.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from app.models.enums import WorkspaceRole
from app.schemas.common import APIModel, ORMModel


class UserBrief(ORMModel):
    id: int
    full_name: str
    username: str


class ProjectRef(ORMModel):
    key: str
    name: str


class TeamMember(ORMModel):
    id: int
    email: str
    username: str
    full_name: str
    workspace_role: WorkspaceRole
    is_active: bool
    open_task_count: int
    projects: list[ProjectRef]
    created_at: datetime


class UserCreate(APIModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32)
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    workspace_role: WorkspaceRole = WorkspaceRole.MEMBER


class UserUpdate(APIModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    workspace_role: WorkspaceRole | None = None
    is_active: bool | None = None


class ResetPasswordRequest(APIModel):
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class ProfileUpdate(APIModel):
    full_name: str = Field(min_length=1, max_length=120)


class WorkspaceOut(ORMModel):
    name: str


class WorkspaceUpdate(APIModel):
    name: str = Field(min_length=1, max_length=120)

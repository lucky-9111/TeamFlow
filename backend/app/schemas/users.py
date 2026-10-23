from datetime import datetime

from pydantic import EmailStr, Field

from app.core.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from app.models.enums import ProjectRole, WorkspaceRole
from app.schemas.common import APIModel, ORMModel


class UserBrief(ORMModel):
    id: int
    username: str
    full_name: str


class MemberProject(APIModel):
    key: str
    name: str
    role: ProjectRole


class TeamMember(ORMModel):
    id: int
    email: str
    username: str
    full_name: str
    workspace_role: WorkspaceRole
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    open_task_count: int = 0
    projects: list[MemberProject] = []


class CreateUserRequest(APIModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32)
    full_name: str = Field(min_length=1, max_length=120)
    workspace_role: WorkspaceRole = WorkspaceRole.MEMBER
    temporary_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class UpdateUserRequest(APIModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    workspace_role: WorkspaceRole | None = None


class ResetPasswordRequest(APIModel):
    temporary_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class UpdateProfileRequest(APIModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)


class Workspace(ORMModel):
    name: str


class UpdateWorkspaceRequest(APIModel):
    name: str = Field(min_length=1, max_length=120)

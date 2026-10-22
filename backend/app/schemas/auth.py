from datetime import datetime

from pydantic import EmailStr, Field

from app.core.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from app.models.enums import WorkspaceRole
from app.schemas.common import APIModel, ORMModel


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class ChangePasswordRequest(APIModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class CurrentUser(ORMModel):
    id: int
    email: str
    username: str
    full_name: str
    workspace_role: WorkspaceRole
    must_change_password: bool
    timezone: str
    last_login_at: datetime | None


class LoginResponse(APIModel):
    user: CurrentUser
    csrf_token: str


class CsrfResponse(APIModel):
    csrf_token: str

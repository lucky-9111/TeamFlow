from fastapi import APIRouter, Query, Response, status

from app.api.deps import DB, CurrentUser, require_action
from app.core.permissions import Action
from app.schemas.users import (
    CreateUserRequest,
    ResetPasswordRequest,
    TeamMember,
    UpdateUserRequest,
    UpdateWorkspaceRequest,
    Workspace,
)
from app.services import users as user_service

router = APIRouter(tags=["team"])


@router.get("/users", response_model=list[TeamMember])
def list_users(
    _: CurrentUser,
    db: DB,
    q: str | None = Query(default=None, max_length=100),
    include_inactive: bool = False,
) -> list[TeamMember]:
    return user_service.list_team(db, q=q, include_inactive=include_inactive)


def _one(db, user_id: int) -> TeamMember:
    return user_service.list_team(db, q=None, include_inactive=True, user_id=user_id)[0]


@router.post("/users", response_model=TeamMember, status_code=status.HTTP_201_CREATED)
def create_user(body: CreateUserRequest, db: DB, admin=require_action(Action.USER_MANAGE)) -> TeamMember:
    user = user_service.admin_create_user(db, admin, body)
    return _one(db, user.id)


@router.patch("/users/{user_id}", response_model=TeamMember)
def update_user(
    user_id: int, body: UpdateUserRequest, db: DB, admin=require_action(Action.USER_MANAGE)
) -> TeamMember:
    user_service.admin_update_user(db, admin, user_id, body)
    return _one(db, user_id)


@router.post("/users/{user_id}/deactivate", response_model=TeamMember)
def deactivate_user(user_id: int, db: DB, admin=require_action(Action.USER_MANAGE)) -> TeamMember:
    user_service.set_active(db, admin, user_id, False)
    return _one(db, user_id)


@router.post("/users/{user_id}/activate", response_model=TeamMember)
def activate_user(user_id: int, db: DB, admin=require_action(Action.USER_MANAGE)) -> TeamMember:
    user_service.set_active(db, admin, user_id, True)
    return _one(db, user_id)


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int, body: ResetPasswordRequest, db: DB, admin=require_action(Action.USER_MANAGE)
) -> Response:
    user_service.reset_password(db, admin, user_id, body.temporary_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/workspace", response_model=Workspace)
def get_workspace(_: CurrentUser, db: DB) -> Workspace:
    return Workspace.model_validate(user_service.get_workspace(db))


@router.patch("/workspace", response_model=Workspace)
def update_workspace(
    body: UpdateWorkspaceRequest, db: DB, admin=require_action(Action.WORKSPACE_MANAGE)
) -> Workspace:
    return Workspace.model_validate(user_service.update_workspace(db, admin, body.name))

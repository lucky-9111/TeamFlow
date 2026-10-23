from fastapi import APIRouter, Response, status

from app.api.deps import DB, CurrentUser, require_action
from app.core.permissions import Action
from app.schemas.user import ResetPasswordRequest, TeamMember, UserCreate, UserUpdate
from app.services import users as user_svc
from app.services import workspace as svc

router = APIRouter(prefix="/users", tags=["users"])


def _member(db, viewer, user_id: int) -> TeamMember:
    return next(m for m in svc.team(db, viewer) if m.id == user_id)


@router.get("", response_model=list[TeamMember])
def list_team(db: DB, user: CurrentUser):
    return svc.team(db, user)


@router.post(
    "",
    response_model=TeamMember,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_action(Action.USER_MANAGE)],
)
def create_user(body: UserCreate, db: DB, user: CurrentUser):
    created = user_svc.create_user(
        db,
        email=body.email,
        username=body.username,
        full_name=body.full_name,
        password=body.password,
        workspace_role=body.workspace_role,
        must_change_password=True,
    )
    db.commit()
    return _member(db, user, created.id)


@router.patch("/{user_id}", response_model=TeamMember)
def update_user(user_id: int, body: UserUpdate, db: DB, user: CurrentUser):
    svc.update_user(db, user, user_id, body.model_dump(exclude_unset=True))
    return _member(db, user, user_id)


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(user_id: int, body: ResetPasswordRequest, db: DB, user: CurrentUser) -> Response:
    svc.reset_password(db, user, user_id, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

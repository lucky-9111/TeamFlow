from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DB, CurrentUser
from app.schemas.common import Page
from app.schemas.task import ActivityOut, DashboardOut, NotificationList, SearchResults
from app.schemas.user import ProjectRef, WorkspaceOut, WorkspaceUpdate
from app.services import tasks as task_svc
from app.services import workspace as svc

router = APIRouter(tags=["workspace"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: DB, user: CurrentUser):
    return svc.dashboard(db, user)


@router.get("/activity", response_model=Page[ActivityOut])
def activity(
    db: DB,
    user: CurrentUser,
    project: Annotated[str | None, Query(max_length=10)] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
):
    return svc.list_activity(db, user, project=project, page=page, page_size=page_size)


@router.get("/search", response_model=SearchResults)
def search(db: DB, user: CurrentUser, q: Annotated[str, Query(min_length=1, max_length=100)]):
    tasks, projects = task_svc.search(db, user, q)
    return SearchResults(tasks=tasks, projects=[ProjectRef.model_validate(p) for p in projects])


@router.get("/workspace", response_model=WorkspaceOut)
def get_workspace(db: DB, user: CurrentUser):
    return svc.get_workspace(db)


@router.patch("/workspace", response_model=WorkspaceOut)
def update_workspace(body: WorkspaceUpdate, db: DB, user: CurrentUser):
    return svc.rename_workspace(db, user, body.name)


@router.get("/notifications", response_model=NotificationList)
def notifications(db: DB, user: CurrentUser, unread: bool = False):
    return svc.list_notifications(db, user, unread_only=unread)


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
def read_all(db: DB, user: CurrentUser) -> Response:
    svc.mark_read(db, user, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def read_one(notification_id: int, db: DB, user: CurrentUser) -> Response:
    svc.mark_read(db, user, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

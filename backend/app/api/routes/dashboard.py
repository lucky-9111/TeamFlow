from fastapi import APIRouter, Query, Response, status

from app.api.deps import DB, CurrentUser
from app.schemas.common import Page
from app.schemas.dashboard import Dashboard, NotificationOut, SearchResults, UnreadCount
from app.schemas.tasks import ActivityOut
from app.services import dashboard as dashboard_service
from app.services import notifications as notification_service

router = APIRouter(tags=["overview"])


@router.get("/dashboard", response_model=Dashboard)
def get_dashboard(user: CurrentUser, db: DB) -> Dashboard:
    return dashboard_service.dashboard(db, user)


@router.get("/activity", response_model=Page[ActivityOut])
def get_activity(
    user: CurrentUser,
    db: DB,
    project: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
) -> Page[ActivityOut]:
    return dashboard_service.activity_feed(db, user, project=project, page=page, page_size=page_size)


@router.get("/search", response_model=SearchResults)
def search(user: CurrentUser, db: DB, q: str = Query(min_length=1, max_length=200)) -> SearchResults:
    return dashboard_service.search(db, user, q)


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    user: CurrentUser, db: DB, unread: bool = False, limit: int = Query(default=30, ge=1, le=100)
) -> list[NotificationOut]:
    return notification_service.list_for(db, user, unread_only=unread, limit=limit)


@router.get("/notifications/unread-count", response_model=UnreadCount)
def unread_count(user: CurrentUser, db: DB) -> UnreadCount:
    return UnreadCount(count=notification_service.unread_count(db, user))


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
def read_all(user: CurrentUser, db: DB) -> Response:
    notification_service.mark_all_read(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(notification_id: int, user: CurrentUser, db: DB) -> Response:
    notification_service.mark_read(db, user, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

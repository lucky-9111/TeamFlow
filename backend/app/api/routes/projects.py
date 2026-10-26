from fastapi import APIRouter, Query, Response, status

from app.api.deps import DB, CurrentUser
from app.models.enums import TaskPriority, TaskType
from app.schemas.projects import (
    AddMemberRequest,
    CreateProjectRequest,
    ProjectDetail,
    ProjectMemberOut,
    ProjectOut,
    UpdateMemberRequest,
    UpdateProjectRequest,
)
from app.schemas.tasks import Board, CreateTaskRequest, TaskDetail
from app.services import projects as project_service
from app.services import task_relations
from app.services import tasks as task_service
from app.services.access import get_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(user: CurrentUser, db: DB, include_archived: bool = False) -> list[ProjectOut]:
    return project_service.list_projects(db, user, include_archived=include_archived)


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(body: CreateProjectRequest, user: CurrentUser, db: DB) -> ProjectDetail:
    access = project_service.create_project(db, user, body)
    return project_service.detail(db, user, access)


@router.get("/{key}", response_model=ProjectDetail)
def get_project_detail(key: str, user: CurrentUser, db: DB) -> ProjectDetail:
    return project_service.detail(db, user, get_project(db, user, key))


@router.patch("/{key}", response_model=ProjectDetail)
def update_project(key: str, body: UpdateProjectRequest, user: CurrentUser, db: DB) -> ProjectDetail:
    access = get_project(db, user, key)
    project_service.update_project(db, user, access, body)
    return project_service.detail(db, user, access)


@router.post("/{key}/archive", response_model=ProjectDetail)
def archive_project(key: str, user: CurrentUser, db: DB) -> ProjectDetail:
    access = get_project(db, user, key)
    project_service.set_archived(db, user, access, True)
    return project_service.detail(db, user, access)


@router.post("/{key}/unarchive", response_model=ProjectDetail)
def unarchive_project(key: str, user: CurrentUser, db: DB) -> ProjectDetail:
    access = get_project(db, user, key)
    project_service.set_archived(db, user, access, False)
    return project_service.detail(db, user, access)


@router.get("/{key}/members", response_model=list[ProjectMemberOut])
def list_members(key: str, user: CurrentUser, db: DB) -> list[ProjectMemberOut]:
    return project_service.detail(db, user, get_project(db, user, key)).members


@router.post("/{key}/members", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def add_member(key: str, body: AddMemberRequest, user: CurrentUser, db: DB) -> ProjectDetail:
    access = get_project(db, user, key)
    project_service.add_member(db, user, access, body)
    return project_service.detail(db, user, access)


@router.patch("/{key}/members/{user_id}", response_model=ProjectDetail)
def update_member(
    key: str, user_id: int, body: UpdateMemberRequest, user: CurrentUser, db: DB
) -> ProjectDetail:
    access = get_project(db, user, key)
    project_service.update_member(db, user, access, user_id, body)
    return project_service.detail(db, user, access)


@router.delete("/{key}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(key: str, user_id: int, user: CurrentUser, db: DB) -> Response:
    project_service.remove_member(db, user, get_project(db, user, key), user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{key}/tasks", response_model=TaskDetail, status_code=status.HTTP_201_CREATED)
def create_task(key: str, body: CreateTaskRequest, user: CurrentUser, db: DB) -> TaskDetail:
    return task_service.create_task(db, user, get_project(db, user, key), body)


@router.get("/{key}/labels", response_model=list[str])
def project_labels(key: str, user: CurrentUser, db: DB) -> list[str]:
    return task_relations.project_labels(db, get_project(db, user, key).project.id)


@router.get("/{key}/board", response_model=Board)
def get_board(
    key: str,
    user: CurrentUser,
    db: DB,
    assignee: str | None = None,
    q: str | None = Query(default=None, max_length=200),
    priority: list[TaskPriority] | None = Query(default=None),
    type: list[TaskType] | None = Query(default=None),
) -> Board:
    return task_service.board(
        db, user, get_project(db, user, key), assignee=assignee, q=q, priority=priority, type_=type
    )

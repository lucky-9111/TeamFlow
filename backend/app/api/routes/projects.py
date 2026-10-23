from fastapi import APIRouter, Query, Response, status

from app.api.deps import DB, CurrentUser
from app.schemas.project import MemberAdd, ProjectCreate, ProjectDetail, ProjectOut, ProjectUpdate
from app.schemas.task import TaskCreate, TaskOut
from app.services import projects as svc
from app.services import tasks as task_svc

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: DB,
    user: CurrentUser,
    include_archived: bool = False,
    q: str | None = Query(default=None, max_length=100),
):
    return svc.list_projects(db, user, include_archived=include_archived, q=q)


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, db: DB, user: CurrentUser):
    project = svc.create_project(db, user, body)
    return svc.to_detail(db, user, project)


@router.get("/{key}", response_model=ProjectDetail)
def get_project(key: str, db: DB, user: CurrentUser):
    return svc.to_detail(db, user, svc.get_project(db, user, key).project)


@router.patch("/{key}", response_model=ProjectDetail)
def update_project(key: str, body: ProjectUpdate, db: DB, user: CurrentUser):
    project = svc.update_project(db, user, svc.get_project(db, user, key).project, body)
    return svc.to_detail(db, user, project)


@router.post("/{key}/archive", response_model=ProjectDetail)
def archive_project(key: str, db: DB, user: CurrentUser):
    project = svc.set_archived(db, user, svc.get_project(db, user, key).project, True)
    return svc.to_detail(db, user, project)


@router.post("/{key}/unarchive", response_model=ProjectDetail)
def unarchive_project(key: str, db: DB, user: CurrentUser):
    project = svc.set_archived(db, user, svc.get_project(db, user, key).project, False)
    return svc.to_detail(db, user, project)


@router.post("/{key}/members", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def add_member(key: str, body: MemberAdd, db: DB, user: CurrentUser):
    project = svc.get_project(db, user, key).project
    svc.add_member(db, user, project, body.user_id)
    return svc.to_detail(db, user, project)


@router.delete("/{key}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(key: str, user_id: int, db: DB, user: CurrentUser) -> Response:
    svc.remove_member(db, user, svc.get_project(db, user, key).project, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{key}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(key: str, body: TaskCreate, db: DB, user: CurrentUser):
    task = task_svc.create_task(db, user, key, body)
    return task_svc.task_out(task, user, task_svc.member_project_ids(db, user))

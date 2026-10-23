"""Task workflow: which status changes exist, and who may make them.

    todo        -> in_progress
    in_progress -> todo, in_review
    in_review   -> in_progress (changes requested), done
    done        -> in_progress (reopen)

Admins and project managers may make any valid move. The person doing the work (the assignee, or
the reporter while nobody is assigned) moves it through To Do / In Progress / In Review. Testers
(TASK_REVIEW) decide what happens after review and may reopen Done tasks.
"""

from app.core.permissions import Action
from app.models.enums import TaskStatus
from app.models.task import Task
from app.models.user import User
from app.services.access import ProjectAccess

S = TaskStatus

TRANSITIONS: dict[TaskStatus, tuple[TaskStatus, ...]] = {
    S.TODO: (S.IN_PROGRESS,),
    S.IN_PROGRESS: (S.TODO, S.IN_REVIEW),
    S.IN_REVIEW: (S.IN_PROGRESS, S.DONE),
    S.DONE: (S.IN_PROGRESS,),
}

_WORKER_MOVES = {(S.TODO, S.IN_PROGRESS), (S.IN_PROGRESS, S.TODO), (S.IN_PROGRESS, S.IN_REVIEW)}
_REVIEW_MOVES = {(S.IN_REVIEW, S.IN_PROGRESS), (S.IN_REVIEW, S.DONE), (S.DONE, S.IN_PROGRESS)}

LABELS = {S.TODO: "To Do", S.IN_PROGRESS: "In Progress", S.IN_REVIEW: "In Review", S.DONE: "Done"}


def is_valid(from_status: TaskStatus, to_status: TaskStatus) -> bool:
    return to_status in TRANSITIONS[from_status]


def _is_worker(user: User, task: Task) -> bool:
    if task.assignee_id is not None:
        return task.assignee_id == user.id
    return task.reporter_id == user.id


def may_move(user: User, access: ProjectAccess, task: Task, to_status: TaskStatus) -> bool:
    move = (task.status, to_status)
    if not is_valid(*move) or access.project.archived_at is not None:
        return False
    if access.can(user, Action.TASK_TRANSITION_ANY):
        return True
    if move in _WORKER_MOVES and _is_worker(user, task) and access.can(user, Action.PROJECT_VIEW):
        return True
    return move in _REVIEW_MOVES and access.can(user, Action.TASK_REVIEW)


def allowed_transitions(user: User, access: ProjectAccess, task: Task) -> list[TaskStatus]:
    return [s for s in TRANSITIONS[task.status] if may_move(user, access, task, s)]

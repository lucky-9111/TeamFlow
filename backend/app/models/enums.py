from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class WorkspaceRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class ProjectRole(StrEnum):
    MANAGER = "manager"
    DEVELOPER = "developer"
    TESTER = "tester"
    DESIGNER = "designer"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"


class TaskType(StrEnum):
    TASK = "task"
    BUG = "bug"
    STORY = "story"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


PRIORITY_RANK = {
    TaskPriority.LOW: 0,
    TaskPriority.MEDIUM: 1,
    TaskPriority.HIGH: 2,
    TaskPriority.URGENT: 3,
}


class NotificationType(StrEnum):
    TASK_ASSIGNED = "task_assigned"
    TASK_STATUS = "task_status"
    TASK_COMMENT = "task_comment"
    PROJECT_ADDED = "project_added"
    TASK_DUE = "task_due"


def str_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Portable enum column: VARCHAR + CHECK constraint, stores the enum *values*."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda cls: [m.value for m in cls],
        validate_strings=True,
    )

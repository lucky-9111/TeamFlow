from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class WorkspaceRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"


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


class TaskType(StrEnum):
    TASK = "task"
    BUG = "bug"
    STORY = "story"


STATUS_LABELS = {
    TaskStatus.TODO: "To Do",
    TaskStatus.IN_PROGRESS: "In Progress",
    TaskStatus.IN_REVIEW: "In Review",
    TaskStatus.DONE: "Done",
}


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

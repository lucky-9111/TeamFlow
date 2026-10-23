from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UTCDateTime, utcnow
from app.models.enums import TaskPriority, TaskStatus, TaskType, str_enum
from app.models.project import Project
from app.models.user import User


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("project_id", "number"),
        Index("ix_tasks_project_status", "project_id", "status"),
        Index("ix_tasks_assignee_status", "assignee_id", "status"),
        Index("ix_tasks_due_date", "due_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    type: Mapped[TaskType] = mapped_column(
        str_enum(TaskType, "task_type"), default=TaskType.TASK, nullable=False
    )
    status: Mapped[TaskStatus] = mapped_column(
        str_enum(TaskStatus, "task_status"), default=TaskStatus.TODO, nullable=False
    )
    priority: Mapped[TaskPriority] = mapped_column(
        str_enum(TaskPriority, "task_priority"), default=TaskPriority.MEDIUM, nullable=False
    )
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    project: Mapped[Project] = relationship()
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    creator: Mapped[User] = relationship(foreign_keys=[creator_id])
    comments: Mapped[list["TaskComment"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def key(self) -> str:
        return f"{self.project.key}-{self.number}"


class TaskComment(TimestampMixin, Base):
    __tablename__ = "task_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    task: Mapped[Task] = relationship(back_populates="comments")
    author: Mapped[User] = relationship()


class Activity(Base):
    """Append-only history. Task rows cascade away with their task; project-level rows stay."""

    __tablename__ = "activities"
    __table_args__ = (Index("ix_activities_project_created", "project_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    field: Mapped[str | None] = mapped_column(String(40))
    old_value: Mapped[str | None] = mapped_column(String(255))
    new_value: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    actor: Mapped[User] = relationship()
    project: Mapped[Project] = relationship()
    task: Mapped[Task | None] = relationship()

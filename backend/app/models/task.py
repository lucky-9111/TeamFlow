from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[TaskType] = mapped_column(
        str_enum(TaskType, "task_type"), default=TaskType.TASK, nullable=False
    )
    status: Mapped[TaskStatus] = mapped_column(
        str_enum(TaskStatus, "task_status"), default=TaskStatus.TODO, nullable=False
    )
    priority: Mapped[TaskPriority] = mapped_column(
        str_enum(TaskPriority, "task_priority"), default=TaskPriority.MEDIUM, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    # One level only: a subtask's parent must itself be a top-level task (enforced in the service).
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Optimistic concurrency: a stale update raises StaleDataError, mapped to 409 in the service.
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    __mapper_args__ = {"version_id_col": version}

    project: Mapped[Project] = relationship()
    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    parent: Mapped["Task | None"] = relationship(remote_side=[id])
    labels: Mapped[list["TaskLabel"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="TaskLabel.name"
    )
    watchers: Mapped[list["TaskWatcher"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)

    @property
    def key(self) -> str:
        return f"{self.project.key}-{self.number}"


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    author: Mapped[User] = relationship()


class ActivityEvent(Base):
    """Append-only history for projects and tasks. Task history is the rows with this task_id."""

    __tablename__ = "activity_events"
    __table_args__ = (Index("ix_activity_events_project_created", "project_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    field: Mapped[str | None] = mapped_column(String(40))
    old_value: Mapped[str | None] = mapped_column(String(255))
    new_value: Mapped[str | None] = mapped_column(String(255))
    # Readable label of the target ("TF-12 Fix login") so the feed survives later renames/deletes.
    target: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    actor: Mapped[User] = relationship()
    project: Mapped[Project | None] = relationship()
    task: Mapped[Task | None] = relationship()


class TaskDependency(Base):
    """`task` depends on `depends_on`: the prerequisite should be finished first. Same project only."""

    __tablename__ = "task_dependencies"
    __table_args__ = (CheckConstraint("task_id != depends_on_id", name="no_self_dependency"),)

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    depends_on_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class TaskLabel(Base):
    """Names are stored lower-case; the primary key stops the same label twice on one task."""

    __tablename__ = "task_labels"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(30), primary_key=True, index=True)


class TaskWatcher(Base):
    __tablename__ = "task_watchers"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    user: Mapped[User] = relationship()


class TaskReminder(Base):
    """One row per (task, due date) reminder sent. The primary key makes the reminder job idempotent:
    re-running it, or two runs overlapping, can never send the same reminder twice."""

    __tablename__ = "task_reminders"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    due_date: Mapped[date] = mapped_column(Date, primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

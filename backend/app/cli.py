"""Operational commands. Run from backend/:  python -m app.cli <command> --help"""

import argparse
import getpass
import os
import sys
from datetime import date, timedelta

from sqlalchemy import delete, or_, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models import AuthSession, LoginAttempt, Project, User, Workspace
from app.models.base import utcnow
from app.models.enums import ProjectRole, TaskPriority, TaskStatus, TaskType, WorkspaceRole
from app.schemas.projects import AddMemberRequest, CreateProjectRequest
from app.schemas.tasks import CreateTaskRequest, TransitionRequest
from app.services import projects as project_service
from app.services import reminders as reminder_service
from app.services import tasks as task_service
from app.services.access import get_project, get_task
from app.services.users import create_user


def _read_password() -> str:
    env_password = os.environ.get("TEAMFLOW_ADMIN_PASSWORD")
    if env_password:
        return env_password
    if not sys.stdin.isatty():
        sys.exit("No TTY: set TEAMFLOW_ADMIN_PASSWORD to provide the password non-interactively.")
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    return password


def cmd_create_admin(args: argparse.Namespace) -> None:
    """Bootstrap the workspace and its first admin. Refuses once any admin exists."""
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.workspace_role == WorkspaceRole.ADMIN)):
            sys.exit("An admin already exists. Add further admins from the Team page.")
        password = _read_password()
        try:
            if db.scalar(select(Workspace.id)) is None:
                db.add(Workspace(name=args.workspace_name, settings={}))
            user = create_user(
                db,
                email=args.email,
                username=args.username,
                full_name=args.full_name,
                password=password,
                workspace_role=WorkspaceRole.ADMIN,
                must_change_password=False,
            )
            db.commit()
        except AppError as exc:
            sys.exit(f"Error: {exc.message}")
        print(f"Created admin {user.email} (id {user.id}).")


def cmd_cleanup(args: argparse.Namespace) -> None:
    """Delete expired/revoked sessions and old login attempts. Safe to run from cron."""
    now = utcnow()
    with SessionLocal() as db:
        sessions = db.execute(
            delete(AuthSession).where(
                or_(AuthSession.expires_at < now, AuthSession.revoked_at < now - timedelta(days=1))
            )
        ).rowcount
        attempts = db.execute(
            delete(LoginAttempt).where(LoginAttempt.created_at < now - timedelta(days=args.attempt_days))
        ).rowcount
        db.commit()
    print(f"Removed {sessions} sessions and {attempts} login attempts.")


DEMO_PASSWORD = "teamflow-demo-123"  # noqa: S105 - dev-only sample accounts; seed-dev refuses in production
DEMO_USERS = [
    ("rahul@example.com", "rahul", "Rahul Sharma", ProjectRole.DEVELOPER),
    ("priya@example.com", "priya", "Priya Verma", ProjectRole.TESTER),
    ("amit@example.com", "amit", "Amit Patel", ProjectRole.DEVELOPER),
    ("sneha@example.com", "sneha", "Sneha Iyer", ProjectRole.DESIGNER),
]

# (project, title, type, priority, assignee username or None, status, due in days or None)
DEMO_TASKS = [
    ("TF", "Set up login page", TaskType.STORY, TaskPriority.HIGH, "rahul", TaskStatus.DONE, -6),
    ("TF", "Design dashboard layout", TaskType.TASK, TaskPriority.MEDIUM, "sneha", TaskStatus.DONE, -3),
    ("TF", "Kanban board drag and drop", TaskType.STORY, TaskPriority.HIGH, "rahul", TaskStatus.IN_REVIEW, 1),
    ("TF", "Task comments API", TaskType.TASK, TaskPriority.MEDIUM, "amit", TaskStatus.IN_PROGRESS, 3),
    (
        "TF",
        "Password reset shows wrong error",
        TaskType.BUG,
        TaskPriority.URGENT,
        "amit",
        TaskStatus.TODO,
        -1,
    ),
    ("TF", "Notifications dropdown", TaskType.TASK, TaskPriority.LOW, None, TaskStatus.TODO, 10),
    ("TF", "Team page avatars", TaskType.TASK, TaskPriority.LOW, "sneha", TaskStatus.IN_PROGRESS, 5),
    ("TF", "Write setup guide", TaskType.TASK, TaskPriority.MEDIUM, "priya", TaskStatus.TODO, None),
    ("MOB", "App onboarding screens", TaskType.STORY, TaskPriority.HIGH, "sneha", TaskStatus.IN_PROGRESS, 4),
    (
        "MOB",
        "Crash on Android 12 when offline",
        TaskType.BUG,
        TaskPriority.URGENT,
        "rahul",
        TaskStatus.TODO,
        2,
    ),
    ("MOB", "Push notification permissions", TaskType.TASK, TaskPriority.MEDIUM, None, TaskStatus.TODO, 14),
]

_PATH = {
    TaskStatus.TODO: [],
    TaskStatus.IN_PROGRESS: [TaskStatus.IN_PROGRESS],
    TaskStatus.IN_REVIEW: [TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW],
    TaskStatus.DONE: [TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW, TaskStatus.DONE],
}


def cmd_seed_dev(args: argparse.Namespace) -> None:
    """Sample users, projects and tasks for local development. Safe to run repeatedly."""
    if get_settings().env == "production":
        sys.exit("seed-dev is for development only and refuses to run in production.")
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.workspace_role == WorkspaceRole.ADMIN).order_by(User.id))
        if admin is None:
            sys.exit("Create an admin first: python -m app.cli create-admin ...")
        if db.scalar(select(Project.id).where(Project.key.in_(["TF", "MOB"]))):
            sys.exit("Sample data already exists (projects TF / MOB). Nothing to do.")

        users = {}
        for email, username, full_name, _ in DEMO_USERS:
            existing = db.scalar(select(User).where(User.email == email))
            users[username] = existing or create_user(
                db,
                email=email,
                username=username,
                full_name=full_name,
                password=DEMO_PASSWORD,
                must_change_password=False,
            )
        db.commit()

        for key, name, description in (
            ("TF", "TeamFlow Web", "The TeamFlow web application."),
            ("MOB", "Mobile App", "Companion mobile app for field teams."),
        ):
            access = project_service.create_project(
                db,
                admin,
                CreateProjectRequest(
                    key=key, name=name, description=description, start_date=date.today() - timedelta(days=14)
                ),
            )
            for _, username, _, role in DEMO_USERS:
                project_service.add_member(
                    db, admin, access, AddMemberRequest(user_id=users[username].id, role=role)
                )

        today = date.today()
        for key, title, type_, priority, assignee, final_status, due in DEMO_TASKS:
            access = get_project(db, admin, key)
            created = task_service.create_task(
                db,
                admin,
                access,
                CreateTaskRequest(
                    title=title,
                    type=type_,
                    priority=priority,
                    assignee_id=users[assignee].id if assignee else None,
                    due_date=today + timedelta(days=due) if due is not None else None,
                ),
            )
            for step in _PATH[final_status]:
                task_access = get_task(db, admin, created.key)
                task_service.transition(
                    db,
                    admin,
                    task_access,
                    TransitionRequest(to_status=step, version=task_access.task.version),
                )
    print(f"Created sample projects TF and MOB with {len(DEMO_TASKS)} tasks.")
    print(f"Sample users ({', '.join(u[0] for u in DEMO_USERS)}) use the password: {DEMO_PASSWORD}")


def cmd_send_due_reminders(args: argparse.Namespace) -> None:
    """Notify assignees and watchers about tasks due soon. Run once a day; safe to re-run."""
    with SessionLocal() as db:
        count = reminder_service.send_due_reminders(db, date.today(), days_ahead=args.days_ahead)
    print(f"Sent due-date reminders for {count} tasks.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-admin", help="create the workspace and its first admin")
    p.add_argument("--email", required=True)
    p.add_argument("--username", required=True)
    p.add_argument("--full-name", required=True)
    p.add_argument("--workspace-name", default="TeamFlow")
    p.set_defaults(func=cmd_create_admin)

    p = sub.add_parser("seed-dev", help="create sample users, projects and tasks (development only)")
    p.set_defaults(func=cmd_seed_dev)

    p = sub.add_parser("cleanup", help="prune expired sessions and old login attempts")
    p.add_argument("--attempt-days", type=int, default=30)
    p.set_defaults(func=cmd_cleanup)

    p = sub.add_parser("send-due-reminders", help="notify about tasks due today or soon (run daily)")
    p.add_argument("--days-ahead", type=int, default=1, choices=range(0, 8), metavar="0-7")
    p.set_defaults(func=cmd_send_due_reminders)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

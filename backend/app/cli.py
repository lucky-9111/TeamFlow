"""Operational commands. Run from backend/:  python -m app.cli <command> --help"""

import argparse
import getpass
import os
import sys
from datetime import timedelta

from sqlalchemy import delete, or_, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models import AuthSession, LoginAttempt, Project, Task, User, Workspace
from app.models.base import utcnow
from app.models.enums import TaskPriority, TaskStatus, TaskType, WorkspaceRole
from app.schemas.project import ProjectCreate
from app.schemas.task import TaskCreate
from app.services import projects as project_service
from app.services import tasks as task_service
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


DEMO_PASSWORD = "teamflow-demo-1"  # noqa: S105 - development seed data only
DEMO_USERS = [
    ("alice@example.com", "alice", "Alice Johnson"),
    ("bob@example.com", "bob", "Bob Martinez"),
    ("carol@example.com", "carol", "Carol Singh"),
]
DEMO_TASKS = [
    # project, title, type, status, priority, assignee username, due offset (days)
    ("DEMO", "Set up CI pipeline", TaskType.TASK, TaskStatus.DONE, TaskPriority.HIGH, "alice", -3),
    ("DEMO", "Design login screen", TaskType.STORY, TaskStatus.IN_REVIEW, TaskPriority.MEDIUM, "carol", 2),
    (
        "DEMO",
        "Fix password reset email",
        TaskType.BUG,
        TaskStatus.IN_PROGRESS,
        TaskPriority.URGENT,
        "bob",
        -1,
    ),
    ("DEMO", "Write onboarding docs", TaskType.TASK, TaskStatus.TODO, TaskPriority.LOW, "alice", 9),
    ("DEMO", "Add CSV export", TaskType.STORY, TaskStatus.TODO, TaskPriority.MEDIUM, None, None),
    ("WEB", "Landing page copy", TaskType.TASK, TaskStatus.IN_PROGRESS, TaskPriority.MEDIUM, "carol", 4),
    ("WEB", "Fix mobile nav overflow", TaskType.BUG, TaskStatus.TODO, TaskPriority.HIGH, "bob", 1),
]


def cmd_seed_dev(args: argparse.Namespace) -> None:
    """Create demo users, projects and tasks. Safe to re-run; refuses in production."""
    from datetime import timedelta

    if get_settings().env == "production":
        sys.exit("seed-dev is disabled when TEAMFLOW_ENV=production.")
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.workspace_role == WorkspaceRole.ADMIN).order_by(User.id))
        if admin is None:
            sys.exit("Create the admin first: python -m app.cli create-admin ...")
        people = {}
        for email, username, full_name in DEMO_USERS:
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                user = create_user(
                    db,
                    email=email,
                    username=username,
                    full_name=full_name,
                    password=DEMO_PASSWORD,
                    must_change_password=False,
                )
            people[username] = user
        db.commit()

        for key, name in (("DEMO", "Demo Project"), ("WEB", "Website")):
            if db.scalar(select(Project.id).where(Project.key == key)) is None:
                project_service.create_project(db, admin, ProjectCreate(key=key, name=name))
            project = db.scalar(select(Project).where(Project.key == key))
            for user in people.values():
                if not project_service.is_member(db, project.id, user.id):
                    project_service.add_member(db, admin, project, user.id)

        today = utcnow().date()
        for key, title, kind, status, priority, who, due in DEMO_TASKS:
            exists = db.scalar(select(Task.id).join(Project).where(Project.key == key, Task.title == title))
            if exists:
                continue
            task_service.create_task(
                db,
                admin,
                key,
                TaskCreate(
                    title=title,
                    type=kind,
                    status=status,
                    priority=priority,
                    assignee_id=people[who].id if who else None,
                    due_date=today + timedelta(days=due) if due is not None else None,
                ),
            )
    print(f"Seeded demo data. Demo users alice/bob/carol use password '{DEMO_PASSWORD}'.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-admin", help="create the workspace and its first admin")
    p.add_argument("--email", required=True)
    p.add_argument("--username", required=True)
    p.add_argument("--full-name", required=True)
    p.add_argument("--workspace-name", default="TeamFlow")
    p.set_defaults(func=cmd_create_admin)

    p = sub.add_parser("cleanup", help="prune expired sessions and old login attempts")
    p.add_argument("--attempt-days", type=int, default=30)
    p.set_defaults(func=cmd_cleanup)

    p = sub.add_parser("seed-dev", help="create demo users, projects and tasks (development only)")
    p.set_defaults(func=cmd_seed_dev)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

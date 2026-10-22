"""Operational commands. Run from backend/:  python -m app.cli <command> --help"""

import argparse
import getpass
import os
import sys
from datetime import timedelta

from sqlalchemy import delete, or_, select

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models import AuthSession, LoginAttempt, User, Workspace
from app.models.base import utcnow
from app.models.enums import WorkspaceRole
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

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.cli import main as cli_main
from app.core.permissions import Action, can
from app.core.security import hash_password, verify_password
from app.models import AuthSession, User, Workspace
from app.models.enums import ProjectRole, WorkspaceRole


def test_sqlite_foreign_keys_are_enforced(db):
    assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
    db.add(
        AuthSession(
            user_id=999_999,
            token_hash="x" * 64,
            csrf_hash="y" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_timestamps_round_trip_as_aware_utc(db, make_user):
    user = make_user()
    ist = timezone(timedelta(hours=5, minutes=30))
    user.last_login_at = datetime(2026, 1, 1, 12, 0, tzinfo=ist)
    db.commit()
    db.expire_all()
    loaded = db.get(User, user.id)
    assert loaded.last_login_at.tzinfo is not None
    assert loaded.last_login_at == datetime(2026, 1, 1, 6, 30, tzinfo=UTC)
    assert loaded.created_at.tzinfo is not None


def test_naive_datetimes_are_rejected(db, make_user):
    user = make_user()
    user.last_login_at = datetime(2026, 1, 1, 12, 0)
    with pytest.raises(Exception, match="Naive datetimes"):
        db.commit()
    db.rollback()


def test_passwords_are_hashed_with_argon2():
    hashed = hash_password("a-long-password")
    assert hashed.startswith("$argon2id$")
    assert verify_password("a-long-password", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("anything", None)


def test_database_rejects_invalid_enum_values(db, make_user):
    user = make_user()
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE users SET workspace_role = 'superuser' WHERE id = :id"), {"id": user.id})
    db.rollback()


class TestPermissionMatrix:
    def _user(self, role=WorkspaceRole.MEMBER, active=True):
        return User(workspace_role=role, is_active=active)

    def test_admin_can_do_everything(self):
        admin = self._user(WorkspaceRole.ADMIN)
        assert all(can(admin, action) for action in Action)

    def test_non_members_have_no_project_access(self):
        assert not can(self._user(), Action.PROJECT_VIEW, None)

    def test_workspace_actions_are_admin_only(self):
        for role in ProjectRole:
            assert not can(self._user(), Action.USER_MANAGE, role)
            assert not can(self._user(), Action.PROJECT_CREATE, role)

    def test_manager_manages_tasks_but_developer_does_not(self):
        assert can(self._user(), Action.TASK_EDIT_ANY, ProjectRole.MANAGER)
        assert can(self._user(), Action.TASK_DELETE, ProjectRole.MANAGER)
        assert not can(self._user(), Action.TASK_EDIT_ANY, ProjectRole.DEVELOPER)
        assert not can(self._user(), Action.TASK_DELETE, ProjectRole.DEVELOPER)

    def test_testers_review_but_developers_and_designers_do_not(self):
        assert can(self._user(), Action.TASK_REVIEW, ProjectRole.TESTER)
        assert not can(self._user(), Action.TASK_REVIEW, ProjectRole.DEVELOPER)
        assert not can(self._user(), Action.TASK_REVIEW, ProjectRole.DESIGNER)

    def test_every_project_role_can_create_and_comment(self):
        for role in ProjectRole:
            assert can(self._user(), Action.TASK_CREATE, role)
            assert can(self._user(), Action.TASK_COMMENT, role)

    def test_inactive_users_have_no_permissions(self):
        assert not can(self._user(WorkspaceRole.ADMIN, active=False), Action.PROJECT_VIEW)


def test_create_admin_cli_bootstraps_once(db, monkeypatch):
    monkeypatch.setenv("TEAMFLOW_ADMIN_PASSWORD", "admin-password-123")
    args = ["create-admin", "--email", "Boss@Example.com", "--username", "boss", "--full-name", "The Boss"]
    cli_main(args)

    admin = db.scalar(select(User).where(User.username == "boss"))
    assert admin.email == "boss@example.com"
    assert admin.workspace_role == WorkspaceRole.ADMIN
    assert admin.must_change_password is False
    assert db.scalar(select(Workspace.name)) == "TeamFlow"
    db.rollback()  # end this session's transaction so it doesn't hold the SQLite write lock

    with pytest.raises(SystemExit, match="already exists"):
        cli_main([*args[:2], "other@example.com", "--username", "other", "--full-name", "Other"])


def test_create_admin_cli_enforces_password_policy(monkeypatch):
    monkeypatch.setenv("TEAMFLOW_ADMIN_PASSWORD", "short")
    with pytest.raises(SystemExit, match="Password must be"):
        cli_main(["create-admin", "--email", "a@example.com", "--username", "admin", "--full-name", "A"])


def test_seed_dev_creates_sample_data_once(db, make_user):
    from app.models import Task

    make_user(role=WorkspaceRole.ADMIN, username="admin")
    db.rollback()
    cli_main(["seed-dev"])
    assert db.scalar(select(func.count()).select_from(Task)) > 0
    db.rollback()
    with pytest.raises(SystemExit, match="already exists"):
        cli_main(["seed-dev"])

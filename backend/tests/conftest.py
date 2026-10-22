"""Test setup. Environment variables are set *before* any app import so the engine binds to a
throwaway SQLite file in a temp directory. Production/dev databases can never be touched."""

import os
import shutil
import tempfile
from pathlib import Path

_TEST_DIR = Path(tempfile.mkdtemp(prefix="teamflow-tests-"))
os.environ["TEAMFLOW_ENV"] = "test"
os.environ["TEAMFLOW_DATABASE_URL"] = f"sqlite:///{(_TEST_DIR / 'test.db').as_posix()}"
os.environ["TEAMFLOW_UPLOAD_DIR"] = str(_TEST_DIR / "uploads")
os.environ["TEAMFLOW_COOKIE_SECURE"] = "false"
os.environ["TEAMFLOW_CORS_ORIGINS"] = ""

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import BACKEND_DIR, get_settings  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User  # noqa: E402
from app.models.enums import WorkspaceRole  # noqa: E402
from app.services.users import create_user  # noqa: E402

DEFAULT_PASSWORD = "correct-horse-battery"


def _assert_isolated() -> None:
    settings = get_settings()
    assert settings.env == "test", "Tests must run with TEAMFLOW_ENV=test"
    assert str(engine.url.database).startswith(_TEST_DIR.as_posix()), "Test DB is not the temp DB"


@pytest.fixture(scope="session", autouse=True)
def _database():
    _assert_isolated()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_url"] = get_settings().database_url
    command.upgrade(cfg, "head")  # build the schema through real migrations
    yield
    engine.dispose()
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(
        *,
        role: WorkspaceRole = WorkspaceRole.MEMBER,
        password: str = DEFAULT_PASSWORD,
        must_change_password: bool = False,
        is_active: bool = True,
        username: str | None = None,
    ) -> User:
        counter["n"] += 1
        name = username or f"user{counter['n']}"
        user = create_user(
            db,
            email=f"{name}@example.com",
            username=name,
            full_name=name.title(),
            password=password,
            workspace_role=role,
            must_change_password=must_change_password,
        )
        user.is_active = is_active
        db.commit()
        return user

    return _make


def login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD):
    """Log in and configure the client to send the CSRF header like the SPA does."""
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if response.status_code == 200:
        client.headers[get_settings().csrf_header_name] = response.json()["csrf_token"]
    return response

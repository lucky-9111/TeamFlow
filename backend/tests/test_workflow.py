"""End-to-end API tests for projects, tasks, comments, activity, dashboard and permissions."""

import threading
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Task
from app.models.base import utcnow
from app.models.enums import WorkspaceRole
from tests.conftest import login

API = "/api/v1"


@pytest.fixture
def session_for(make_user):
    """Return a logged-in TestClient (own cookie jar) for a freshly created user."""
    clients = []

    def _make(role=WorkspaceRole.MEMBER, username=None):
        user = make_user(role=role, username=username)
        c = TestClient(app)
        assert login(c, user.email).status_code == 200
        clients.append(c)
        c.user = user
        return c

    yield _make
    for c in clients:
        c.close()


@pytest.fixture
def admin(session_for):
    return session_for(WorkspaceRole.ADMIN, "boss")


@pytest.fixture
def alice(session_for):
    return session_for(username="alice")


@pytest.fixture
def bob(session_for):
    return session_for(username="bob")


def make_project(admin, key="TF", members=()):
    r = admin.post(f"{API}/projects", json={"key": key, "name": f"Project {key}"})
    assert r.status_code == 201, r.text
    for m in members:
        assert admin.post(f"{API}/projects/{key}/members", json={"user_id": m.user.id}).status_code == 201
    return r.json()


def make_task(client, key="TF", **fields):
    r = client.post(f"{API}/projects/{key}/tasks", json={"title": "Write docs", **fields})
    assert r.status_code == 201, r.text
    return r.json()


class TestProjects:
    def test_admin_creates_project_and_is_member(self, admin):
        project = make_project(admin)
        assert project["key"] == "TF"
        assert [m["username"] for m in project["members"]] == ["boss"]

    def test_member_cannot_create_project(self, alice):
        r = alice.post(f"{API}/projects", json={"key": "AB", "name": "Nope"})
        assert r.status_code == 403

    def test_duplicate_and_invalid_keys(self, admin):
        make_project(admin)
        assert admin.post(f"{API}/projects", json={"key": "tf", "name": "Again"}).status_code == 409
        assert admin.post(f"{API}/projects", json={"key": "1X", "name": "Bad"}).status_code == 422
        assert admin.post(f"{API}/projects", json={"key": "A", "name": "Short"}).status_code == 422

    def test_non_member_gets_404_not_403(self, admin, alice):
        make_project(admin)
        assert alice.get(f"{API}/projects/TF").status_code == 404
        assert alice.get(f"{API}/projects").json() == []

    def test_adding_member_grants_access(self, admin, alice):
        make_project(admin, members=[alice])
        assert alice.get(f"{API}/projects/TF").status_code == 200
        assert [p["key"] for p in alice.get(f"{API}/projects").json()] == ["TF"]

    def test_member_cannot_manage_members(self, admin, alice, bob):
        make_project(admin, members=[alice])
        r = alice.post(f"{API}/projects/TF/members", json={"user_id": bob.user.id})
        assert r.status_code == 403

    def test_removing_member_unassigns_their_tasks_and_blocks_access(self, admin, alice):
        make_project(admin, members=[alice])
        make_task(admin, assignee_id=alice.user.id)
        assert admin.delete(f"{API}/projects/TF/members/{alice.user.id}").status_code == 204
        assert admin.get(f"{API}/tasks/TF-1").json()["assignee"] is None
        assert alice.get(f"{API}/tasks/TF-1").status_code == 404

    def test_archived_project_is_read_only(self, admin):
        make_project(admin)
        make_task(admin)
        assert admin.post(f"{API}/projects/TF/archive").json()["is_archived"] is True
        assert admin.post(f"{API}/projects/TF/tasks", json={"title": "x"}).status_code == 409
        assert admin.patch(f"{API}/tasks/TF-1", json={"title": "y"}).status_code == 409
        assert admin.get(f"{API}/projects").json() == []
        assert len(admin.get(f"{API}/projects?include_archived=true").json()) == 1


class TestTasks:
    def test_task_keys_increment(self, admin):
        make_project(admin)
        keys = [make_task(admin)["key"] for _ in range(3)]
        assert keys == ["TF-1", "TF-2", "TF-3"]

    def test_keys_unique_under_concurrency(self, admin, db):
        make_project(admin)
        results = []

        def worker():
            c = TestClient(app)
            login(c, admin.user.email)
            for _ in range(3):
                results.append(c.post(f"{API}/projects/TF/tasks", json={"title": "t"}).status_code)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert results == [201] * 12
        db.expire_all()
        numbers = sorted(db.scalars(select(Task.number)))
        db.rollback()
        assert numbers == list(range(1, 13))

    def test_assignee_must_be_project_member(self, admin, alice, bob):
        make_project(admin, members=[alice])
        r = admin.post(f"{API}/projects/TF/tasks", json={"title": "x", "assignee_id": bob.user.id})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "invalid_assignee"

    def test_invalid_enum_values_rejected(self, admin):
        make_project(admin)
        for field, value in (("status", "blocked"), ("priority", "critical"), ("type", "epic")):
            r = admin.post(f"{API}/projects/TF/tasks", json={"title": "x", field: value})
            assert r.status_code == 422, field
        make_task(admin)
        assert admin.patch(f"{API}/tasks/TF-1", json={"status": "archived"}).status_code == 422

    def test_validation_errors(self, admin):
        make_project(admin)
        assert admin.post(f"{API}/projects/TF/tasks", json={"title": ""}).status_code == 422
        assert admin.post(f"{API}/projects/TF/tasks", json={"title": "x" * 201}).status_code == 422
        r = admin.post(
            f"{API}/projects/TF/tasks",
            json={"title": "x", "start_date": "2026-02-02", "due_date": "2026-02-01"},
        )
        assert r.status_code == 422
        assert admin.post(f"{API}/projects/TF/tasks", json={"title": "x", "bogus": 1}).status_code == 422

    def test_status_change_persists_and_is_logged(self, admin, alice, db):
        make_project(admin, members=[alice])
        make_task(alice)
        r = alice.patch(f"{API}/tasks/TF-1", json={"status": "in_progress"})
        assert r.status_code == 200 and r.json()["status"] == "in_progress"

        db.expire_all()
        assert db.scalar(select(Task.status).where(Task.number == 1)) == "in_progress"
        db.rollback()  # end the read transaction; SQLite would otherwise hold the write lock

        history = alice.get(f"{API}/tasks/TF-1/activity").json()
        assert history[0]["action"] == "task.status_changed"
        assert history[0]["summary"] == "moved TF-1 from To Do to In Progress"
        assert history[0]["actor"]["username"] == "alice"
        assert history[-1]["action"] == "task.created"

    def test_done_sets_and_reopen_clears_completed_at(self, admin):
        make_project(admin)
        make_task(admin)
        assert admin.patch(f"{API}/tasks/TF-1", json={"status": "done"}).json()["completed_at"]
        assert admin.patch(f"{API}/tasks/TF-1", json={"status": "todo"}).json()["completed_at"] is None

    def test_assign_and_unassign(self, admin, alice):
        make_project(admin, members=[alice])
        make_task(admin)
        r = admin.patch(f"{API}/tasks/TF-1", json={"assignee_id": alice.user.id})
        assert r.json()["assignee"]["username"] == "alice"
        r = admin.patch(f"{API}/tasks/TF-1", json={"assignee_id": None})
        assert r.json()["assignee"] is None
        actions = [h["summary"] for h in admin.get(f"{API}/tasks/TF-1/activity").json()]
        assert "unassigned TF-1" in actions

    def test_member_cannot_edit_others_tasks(self, admin, alice, bob):
        make_project(admin, members=[alice, bob])
        make_task(admin)
        assert alice.patch(f"{API}/tasks/TF-1", json={"title": "hijack"}).status_code == 403
        task = alice.get(f"{API}/tasks/TF-1").json()
        assert task["can_edit"] is False and task["can_delete"] is False

    def test_assignee_can_edit_but_not_delete(self, admin, alice):
        make_project(admin, members=[alice])
        make_task(admin, assignee_id=alice.user.id)
        assert alice.patch(f"{API}/tasks/TF-1", json={"status": "in_review"}).status_code == 200
        assert alice.delete(f"{API}/tasks/TF-1").status_code == 403

    def test_creator_and_admin_can_delete(self, admin, alice):
        make_project(admin, members=[alice])
        make_task(alice)
        make_task(alice)
        assert alice.delete(f"{API}/tasks/TF-1").status_code == 204
        assert admin.delete(f"{API}/tasks/TF-2").status_code == 204
        assert admin.get(f"{API}/tasks/TF-1").status_code == 404

    def test_idor_on_every_task_endpoint(self, admin, alice):
        make_project(admin)
        make_task(admin)
        for method, path, body in (
            ("get", "/tasks/TF-1", None),
            ("patch", "/tasks/TF-1", {"title": "x"}),
            ("delete", "/tasks/TF-1", None),
            ("get", "/tasks/TF-1/comments", None),
            ("post", "/tasks/TF-1/comments", {"body": "hi"}),
            ("get", "/tasks/TF-1/activity", None),
            ("post", "/projects/TF/tasks", {"title": "x"}),
        ):
            r = getattr(alice, method)(f"{API}{path}", **({"json": body} if body else {}))
            assert r.status_code == 404, (method, path)
        assert alice.get(f"{API}/tasks").json()["total"] == 0
        assert alice.get(f"{API}/search?q=Write").json() == {"tasks": [], "projects": []}
        assert alice.get(f"{API}/activity").json()["total"] == 0

    def test_unknown_task_key_formats(self, admin):
        for key in ("nope", "TF-0x", "TF-999"):
            assert admin.get(f"{API}/tasks/{key}").status_code == 404

    def test_unauthenticated_requests_are_rejected(self, client):
        for path in ("/tasks", "/projects", "/dashboard", "/users", "/activity", "/notifications"):
            assert client.get(f"{API}{path}").status_code == 401

    def test_csrf_required_for_writes(self, admin):
        make_project(admin)
        del admin.headers["X-CSRF-Token"]
        r = admin.post(f"{API}/projects/TF/tasks", json={"title": "x"})
        assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"


class TestListing:
    @pytest.fixture
    def seeded(self, admin, alice):
        make_project(admin, "TF", members=[alice])
        make_project(admin, "WEB")
        make_task(
            admin, title="Login page", priority="high", assignee_id=alice.user.id, due_date="2020-01-01"
        )
        make_task(admin, title="Logout bug", type="bug", priority="urgent", status="done")
        make_task(admin, title="Docs", priority="low", due_date="2099-01-01")
        make_task(admin, "WEB", title="Landing")

    def titles(self, client, query=""):
        return [t["title"] for t in client.get(f"{API}/tasks?{query}").json()["items"]]

    def test_filters(self, admin, alice, seeded):
        assert sorted(self.titles(admin, "project=TF")) == ["Docs", "Login page", "Logout bug"]
        assert self.titles(admin, "status=done") == ["Logout bug"]
        assert sorted(self.titles(admin, "status=done&status=todo&project=WEB")) == ["Landing"]
        assert self.titles(admin, "priority=urgent") == ["Logout bug"]
        assert self.titles(admin, f"assignee={alice.user.id}") == ["Login page"]
        assert self.titles(alice, "assignee=me") == ["Login page"]
        assert sorted(self.titles(admin, "assignee=none&project=TF")) == ["Docs", "Logout bug"]
        assert self.titles(admin, "overdue=true") == ["Login page"]

    def test_search_by_title_and_key(self, admin, seeded):
        assert sorted(self.titles(admin, "q=log")) == ["Login page", "Logout bug"]
        assert self.titles(admin, "q=web-1") == ["Landing"]

    def test_member_only_sees_their_projects(self, alice, seeded):
        assert "Landing" not in self.titles(alice)
        assert len(self.titles(alice)) == 3

    def test_sorting_and_pagination(self, admin, seeded):
        assert self.titles(admin, "project=TF&sort=priority&order=asc") == [
            "Logout bug",
            "Login page",
            "Docs",
        ]
        assert self.titles(admin, "project=TF&sort=due_date&order=asc")[:2] == ["Login page", "Docs"]
        page = admin.get(f"{API}/tasks?page_size=2&page=2").json()
        assert page["total"] == 4 and len(page["items"]) == 2 and page["page"] == 2
        assert admin.get(f"{API}/tasks?sort=password").status_code == 422
        assert admin.get(f"{API}/tasks?page_size=5000").status_code == 422
        assert admin.get(f"{API}/tasks?status=bogus").status_code == 422


class TestCollaboration:
    def test_comments_and_activity(self, admin, alice):
        make_project(admin, members=[alice])
        make_task(admin, assignee_id=alice.user.id)
        r = alice.post(f"{API}/tasks/TF-1/comments", json={"body": "On it"})
        assert r.status_code == 201 and r.json()["author"]["username"] == "alice"
        assert alice.post(f"{API}/tasks/TF-1/comments", json={"body": "  "}).status_code == 422
        assert [c["body"] for c in admin.get(f"{API}/tasks/TF-1/comments").json()] == ["On it"]
        assert admin.get(f"{API}/tasks/TF-1/activity").json()[0]["action"] == "task.commented"

    def test_notifications_for_assignment_and_comments(self, admin, alice):
        make_project(admin, members=[alice])
        make_task(admin, assignee_id=alice.user.id)
        make_task(admin)
        got = alice.get(f"{API}/notifications").json()
        assert got["unread_count"] == 1 and got["items"][0]["kind"] == "assigned"
        assert got["items"][0]["task_key"] == "TF-1"

        alice.post(f"{API}/tasks/TF-2/comments", json={"body": "hi"})
        assert admin.get(f"{API}/notifications").json()["unread_count"] == 1  # creator is told

        # acting on your own task never notifies yourself
        admin.patch(f"{API}/tasks/TF-2", json={"assignee_id": admin.user.id})
        assert admin.get(f"{API}/notifications").json()["unread_count"] == 1

        note_id = got["items"][0]["id"]
        assert alice.post(f"{API}/notifications/{note_id}/read").status_code == 204
        assert alice.get(f"{API}/notifications").json()["unread_count"] == 0
        assert admin.post(f"{API}/notifications/{note_id}/read").status_code == 404

    def test_project_activity_feed(self, admin, alice):
        make_project(admin, members=[alice])
        make_task(alice)
        feed = admin.get(f"{API}/activity?project=TF").json()
        summaries = [e["summary"] for e in feed["items"]]
        assert "created TF-1" in summaries and "created project TF" in summaries
        assert "added Alice to TF" in summaries


class TestDashboardAndTeam:
    def test_dashboard_reflects_database(self, admin, alice):
        make_project(admin, "TF", members=[alice])
        make_project(admin, "OLD")
        admin.post(f"{API}/projects/OLD/archive")
        make_task(admin, assignee_id=alice.user.id, due_date="2020-01-01")  # overdue, alice's
        make_task(admin, due_date=(utcnow() + timedelta(days=2)).date().isoformat())  # upcoming
        make_task(admin, status="done")
        admin.patch(f"{API}/tasks/TF-3", json={"status": "done"})

        d = admin.get(f"{API}/dashboard").json()
        assert d["active_projects"] == 1
        assert d["open_tasks"] == 2
        assert d["my_open_tasks"] == 0
        assert d["overdue_tasks"] == 1
        assert d["completed_recently"] == 1
        assert [t["key"] for t in d["upcoming_deadlines"]] == ["TF-2"]
        assert d["recent_activity"]

        a = alice.get(f"{API}/dashboard").json()
        assert a["my_open_tasks"] == 1 and [t["key"] for t in a["my_tasks"]] == ["TF-1"]

    def test_team_listing_hides_unshared_projects_and_secrets(self, admin, alice, bob):
        make_project(admin, "TF", members=[alice])
        make_project(admin, "SEC", members=[bob])
        make_task(admin, assignee_id=alice.user.id)

        as_alice = {m["username"]: m for m in alice.get(f"{API}/users").json()}
        assert [p["key"] for p in as_alice["boss"]["projects"]] == ["TF"]
        assert as_alice["bob"]["projects"] == []
        assert as_alice["alice"]["open_task_count"] == 1
        assert "password_hash" not in as_alice["alice"]

        as_admin = {m["username"]: m for m in admin.get(f"{API}/users").json()}
        assert [p["key"] for p in as_admin["bob"]["projects"]] == ["SEC"]

    def test_search_returns_projects_and_tasks(self, admin):
        make_project(admin)
        make_task(admin, title="Write docs")
        r = admin.get(f"{API}/search?q=tf").json()
        assert r["projects"] == [{"key": "TF", "name": "Project TF"}]
        assert admin.get(f"{API}/search?q=docs").json()["tasks"][0]["key"] == "TF-1"


class TestUserAdmin:
    def new_user(self, **kw):
        return {
            "email": "new@example.com",
            "username": "newbie",
            "full_name": "New Person",
            "password": "temporary-pass-1",
            **kw,
        }

    def test_admin_creates_user_who_must_change_password(self, admin):
        r = admin.post(f"{API}/users", json=self.new_user())
        assert r.status_code == 201 and r.json()["workspace_role"] == "member"
        c = TestClient(app)
        assert login(c, "new@example.com", "temporary-pass-1").status_code == 200
        r = c.get(f"{API}/tasks")
        assert r.status_code == 403 and r.json()["error"]["code"] == "password_change_required"
        c.close()

    def test_member_cannot_manage_users(self, alice):
        assert alice.post(f"{API}/users", json=self.new_user()).status_code == 403
        assert alice.patch(f"{API}/users/1", json={"is_active": False}).status_code == 403
        assert alice.post(f"{API}/users/1/reset-password", json={"new_password": "x" * 12}).status_code == 403

    def test_duplicate_email_conflicts(self, admin, alice):
        r = admin.post(f"{API}/users", json=self.new_user(email=alice.user.email))
        assert r.status_code == 409

    def test_deactivation_revokes_sessions_and_unassigns(self, admin, alice):
        make_project(admin, members=[alice])
        make_task(admin, assignee_id=alice.user.id)
        r = admin.patch(f"{API}/users/{alice.user.id}", json={"is_active": False})
        assert r.status_code == 200 and r.json()["is_active"] is False
        assert alice.get(f"{API}/tasks").status_code == 401
        assert admin.get(f"{API}/tasks/TF-1").json()["assignee"] is None

    def test_admin_cannot_lock_themselves_out(self, admin):
        r = admin.patch(f"{API}/users/{admin.user.id}", json={"workspace_role": "member"})
        assert r.status_code == 409
        r = admin.patch(f"{API}/users/{admin.user.id}", json={"is_active": False})
        assert r.status_code == 409

    def test_invalid_role_rejected(self, admin, alice):
        assert admin.patch(f"{API}/users/{alice.user.id}", json={"workspace_role": "root"}).status_code == 422

    def test_profile_and_workspace(self, admin, alice, db):
        from app.models import Workspace

        db.add(Workspace(name="Acme", settings={}))
        db.commit()
        assert alice.patch(f"{API}/auth/me", json={"full_name": "Alice A"}).json()["full_name"] == "Alice A"
        assert alice.get(f"{API}/workspace").json() == {"name": "Acme"}
        assert alice.patch(f"{API}/workspace", json={"name": "X"}).status_code == 403
        assert admin.patch(f"{API}/workspace", json={"name": "Renamed"}).json() == {"name": "Renamed"}

from datetime import date, timedelta

import pytest

from app.models.enums import WorkspaceRole
from tests.conftest import login

API = "/api/v1"


@pytest.fixture
def team(client, make_user):
    users = {
        "admin": make_user(role=WorkspaceRole.ADMIN, username="admin"),
        "dev": make_user(username="dev"),
        "dev2": make_user(username="dev2"),
        "tester": make_user(username="tester"),
        "outsider": make_user(username="outsider"),
    }
    login(client, users["admin"].email)
    client.post(f"{API}/projects", json={"key": "TF", "name": "TeamFlow"})
    for name, role in (("dev", "developer"), ("dev2", "developer"), ("tester", "tester")):
        r = client.post(f"{API}/projects/TF/members", json={"user_id": users[name].id, "role": role})
        assert r.status_code == 201
    return users


def _create(client, **fields):
    r = client.post(f"{API}/projects/TF/tasks", json={"title": "Build login", **fields})
    assert r.status_code == 201, r.text
    return r.json()


def _move(client, task, to):
    return client.post(
        f"{API}/tasks/{task['key']}/transitions", json={"to_status": to, "version": task["version"]}
    )


def test_task_keys_are_sequential_per_project(client, team):
    assert [_create(client)["key"] for _ in range(3)] == ["TF-1", "TF-2", "TF-3"]
    client.post(f"{API}/projects", json={"key": "MOB", "name": "Mobile"})
    assert client.post(f"{API}/projects/MOB/tasks", json={"title": "x"}).json()["key"] == "MOB-1"


def test_deleted_task_numbers_are_not_reused(client, team):
    first = _create(client)
    assert client.delete(f"{API}/tasks/{first['key']}").status_code == 204
    assert _create(client)["key"] == "TF-2"


def test_create_task_validates_input(client, team):
    assert client.post(f"{API}/projects/TF/tasks", json={"title": ""}).status_code == 422
    assert client.post(f"{API}/projects/TF/tasks", json={"title": "x", "priority": "asap"}).status_code == 422
    assert client.post(f"{API}/projects/TF/tasks", json={"title": "x", "status": "done"}).status_code == 422
    r = client.post(f"{API}/projects/TF/tasks", json={"title": "x", "assignee_id": team["outsider"].id})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_assignee"
    r = client.post(
        f"{API}/projects/TF/tasks", json={"title": "x", "start_date": "2026-05-10", "due_date": "2026-05-01"}
    )
    assert r.status_code == 422


def test_outsider_cannot_read_or_change_tasks(client, team):
    task = _create(client)
    login(client, team["outsider"].email)
    assert client.get(f"{API}/tasks/{task['key']}").status_code == 404
    assert client.patch(f"{API}/tasks/{task['key']}", json={"version": 1, "title": "x"}).status_code == 404
    assert client.get(f"{API}/tasks").json()["total"] == 0
    assert client.get(f"{API}/search?q=login").json()["tasks"] == []


def test_unauthenticated_requests_are_rejected(client, team):
    task = _create(client)
    client.post(f"{API}/auth/logout")
    client.cookies.clear()
    assert client.get(f"{API}/tasks/{task['key']}").status_code == 401
    assert client.get(f"{API}/dashboard").status_code == 401


class TestWorkflow:
    def test_full_cycle_with_roles(self, client, team):
        task = _create(client, assignee_id=team["dev"].id)

        login(client, team["dev"].email)
        detail = client.get(f"{API}/tasks/{task['key']}").json()
        assert detail["allowed_transitions"] == ["in_progress"]
        task = _move(client, detail, "in_progress").json()
        task = _move(client, task, "in_review").json()
        assert task["allowed_transitions"] == []  # developers can't approve their own work
        assert _move(client, task, "done").status_code == 403

        login(client, team["tester"].email)
        task = client.get(f"{API}/tasks/{task['key']}").json()
        assert set(task["allowed_transitions"]) == {"in_progress", "done"}
        task = _move(client, task, "done").json()
        assert task["status"] == "done"
        assert task["completed_at"] is not None

        task = _move(client, task, "in_progress").json()  # tester reopens
        assert task["completed_at"] is None

    def test_invalid_transition_is_rejected_with_clear_message(self, client, team):
        task = _create(client)
        r = _move(client, task, "done")
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_transition"
        assert "To Do" in r.json()["error"]["message"]

    def test_unknown_status_value_is_rejected(self, client, team):
        task = _create(client)
        assert _move(client, task, "shipped").status_code == 422

    def test_other_developer_cannot_move_someone_elses_task(self, client, team):
        task = _create(client, assignee_id=team["dev"].id)
        login(client, team["dev2"].email)
        assert _move(client, task, "in_progress").status_code == 403

    def test_stale_version_returns_conflict(self, client, team):
        task = _create(client)
        assert _move(client, task, "in_progress").status_code == 200
        r = _move(client, task, "in_progress")  # same old version
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "stale_version"

    def test_status_change_is_logged_and_notifies_assignee(self, client, team):
        task = _create(client, assignee_id=team["dev"].id)
        _move(client, task, "in_progress")
        history = client.get(f"{API}/tasks/{task['key']}/activity").json()
        change = next(e for e in history if e["action"] == "status_changed")
        assert (change["old_value"], change["new_value"]) == ("todo", "in_progress")
        assert change["actor"]["username"] == "admin"

        login(client, team["dev"].email)
        types = [n["type"] for n in client.get(f"{API}/notifications").json()]
        assert "task_status" in types and "task_assigned" in types


class TestEditing:
    def test_assignee_edits_own_task_but_not_others(self, client, team):
        mine = _create(client, assignee_id=team["dev"].id)
        theirs = _create(client, assignee_id=team["dev2"].id)
        login(client, team["dev"].email)
        r = client.patch(f"{API}/tasks/{mine['key']}", json={"version": mine["version"], "priority": "high"})
        assert r.status_code == 200
        assert r.json()["priority"] == "high"
        r = client.patch(f"{API}/tasks/{theirs['key']}", json={"version": theirs["version"], "title": "x"})
        assert r.status_code == 403
        assert client.delete(f"{API}/tasks/{mine['key']}").status_code == 403

    def test_patch_cannot_change_status(self, client, team):
        task = _create(client)
        r = client.patch(f"{API}/tasks/{task['key']}", json={"version": task["version"], "status": "done"})
        assert r.status_code == 422

    def test_reassign_logs_and_notifies(self, client, team):
        task = _create(client, assignee_id=team["dev"].id)
        r = client.patch(
            f"{API}/tasks/{task['key']}", json={"version": task["version"], "assignee_id": team["dev2"].id}
        )
        assert r.json()["assignee"]["username"] == "dev2"
        history = client.get(f"{API}/tasks/{task['key']}/activity").json()
        assert history[0]["action"] == "task_assigned"
        assert history[0]["new_value"] == "Dev2"
        task = r.json()
        r = client.patch(f"{API}/tasks/{task['key']}", json={"version": task["version"], "assignee_id": None})
        assert r.json()["assignee"] is None


class TestComments:
    def test_comment_flow(self, client, team):
        task = _create(client, assignee_id=team["dev"].id)
        login(client, team["tester"].email)
        r = client.post(f"{API}/tasks/{task['key']}/comments", json={"body": "Works on Chrome?"})
        assert r.status_code == 201
        comment = r.json()
        assert comment["can_edit"] is True

        login(client, team["dev"].email)
        comments = client.get(f"{API}/tasks/{task['key']}/comments").json()
        assert [c["body"] for c in comments] == ["Works on Chrome?"]
        assert comments[0]["can_edit"] is False
        assert client.patch(f"{API}/comments/{comment['id']}", json={"body": "x"}).status_code == 403
        assert any(n["type"] == "task_comment" for n in client.get(f"{API}/notifications").json())

        login(client, team["admin"].email)  # managers can moderate
        assert client.delete(f"{API}/comments/{comment['id']}").status_code == 204

    def test_empty_comment_rejected(self, client, team):
        task = _create(client)
        assert client.post(f"{API}/tasks/{task['key']}/comments", json={"body": "   "}).status_code == 422


class TestListingAndDashboard:
    def test_filters_sort_and_pagination(self, client, team):
        today = date.today()
        _create(
            client,
            title="Fix crash",
            type="bug",
            priority="urgent",
            assignee_id=team["dev"].id,
            due_date=(today - timedelta(days=3)).isoformat(),
        )
        _create(client, title="Write docs", priority="low")
        _create(client, title="Add search", priority="high", due_date=(today + timedelta(days=2)).isoformat())

        def keys(query):
            return [t["title"] for t in client.get(f"{API}/tasks?{query}").json()["items"]]

        assert keys("type=bug") == ["Fix crash"]
        assert keys("q=docs") == ["Write docs"]
        assert keys("q=TF-3") == ["Add search"]
        assert keys(f"assignee={team['dev'].id}") == ["Fix crash"]
        assert keys("assignee=none&sort=priority&order=desc") == ["Add search", "Write docs"]
        assert keys("overdue=true") == ["Fix crash"]
        assert keys("sort=due&order=asc") == ["Fix crash", "Add search", "Write docs"]
        page = client.get(f"{API}/tasks?page_size=2&page=2").json()
        assert (page["total"], len(page["items"])) == (3, 1)
        assert client.get(f"{API}/tasks?page_size=1000").status_code == 422

    def test_board_groups_by_status(self, client, team):
        task = _create(client)
        _move(client, task, "in_progress")
        _create(client, title="Second")
        board = client.get(f"{API}/projects/TF/board").json()
        columns = {c["status"]: [t["title"] for t in c["tasks"]] for c in board["columns"]}
        assert columns == {"todo": ["Second"], "in_progress": ["Build login"], "in_review": [], "done": []}

    def test_dashboard_counts_come_from_data(self, client, team):
        login(client, team["dev"].email)
        _create(client, assignee_id=team["dev"].id, due_date=(date.today() - timedelta(days=1)).isoformat())
        _create(client)
        stats = client.get(f"{API}/dashboard").json()["stats"]
        assert stats == {
            "active_projects": 1,
            "open_tasks": 2,
            "my_open_tasks": 1,
            "overdue_tasks": 1,
            "completed_last_7_days": 0,
        }
        feed = client.get(f"{API}/activity").json()
        assert feed["total"] >= 2

    def test_search_finds_projects_and_tasks(self, client, team):
        _create(client, title="Payment gateway")
        results = client.get(f"{API}/search?q=pay").json()
        assert [t["key"] for t in results["tasks"]] == ["TF-1"]
        assert client.get(f"{API}/search?q=team").json()["projects"] == [{"key": "TF", "name": "TeamFlow"}]

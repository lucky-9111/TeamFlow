import pytest

from app.models.enums import WorkspaceRole
from tests.conftest import login

API = "/api/v1"


@pytest.fixture
def team(client, make_user):
    users = {
        "admin": make_user(role=WorkspaceRole.ADMIN, username="admin"),
        "dev": make_user(username="dev"),
        "outsider": make_user(username="outsider"),
    }
    login(client, users["admin"].email)
    client.post(f"{API}/projects", json={"key": "TF", "name": "TeamFlow"})
    r = client.post(f"{API}/projects/TF/members", json={"user_id": users["dev"].id, "role": "developer"})
    assert r.status_code == 201
    return users


def _create(client, **fields):
    r = client.post(f"{API}/projects/TF/tasks", json={"title": "Build login", **fields})
    assert r.status_code == 201, r.text
    return r.json()


def _subtask(client, parent_key, title="Design button"):
    return client.post(f"{API}/tasks/{parent_key}/subtasks", json={"title": title})


def _move(client, task, *statuses):
    for to in statuses:
        r = client.post(
            f"{API}/tasks/{task['key']}/transitions", json={"to_status": to, "version": task["version"]}
        )
        assert r.status_code == 200, r.text
        task = r.json()
    return task


def test_create_subtask_and_progress(client, team):
    parent = _create(client)
    first = _subtask(client, parent["key"])
    assert first.status_code == 201
    assert first.json()["parent_key"] == parent["key"]
    _subtask(client, parent["key"], "Check password")

    summary = client.get(f"{API}/tasks/{parent['key']}/subtasks").json()
    assert (summary["done"], summary["total"]) == (0, 2)

    _move(client, first.json(), "in_progress", "in_review", "done")
    summary = client.get(f"{API}/tasks/{parent['key']}/subtasks").json()
    assert (summary["done"], summary["total"]) == (1, 2)
    assert [t["title"] for t in summary["items"]] == ["Design button", "Check password"]


def test_top_level_task_has_no_parent(client, team):
    task = _create(client)
    assert task["parent_key"] is None
    assert client.get(f"{API}/tasks/{task['key']}/subtasks").json() == {"items": [], "done": 0, "total": 0}


def test_subtask_cannot_have_subtasks(client, team):
    parent = _create(client)
    child = _subtask(client, parent["key"]).json()
    r = _subtask(client, child["key"])
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "nested_subtask"


def test_parent_with_subtasks_cannot_be_deleted(client, team):
    parent = _create(client)
    child = _subtask(client, parent["key"]).json()
    r = client.delete(f"{API}/tasks/{parent['key']}")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "has_subtasks"

    assert client.delete(f"{API}/tasks/{child['key']}").status_code == 204
    assert client.delete(f"{API}/tasks/{parent['key']}").status_code == 204


def test_subtask_validates_input(client, team):
    parent = _create(client)
    assert client.post(f"{API}/tasks/{parent['key']}/subtasks", json={"title": ""}).status_code == 422
    r = client.post(
        f"{API}/tasks/{parent['key']}/subtasks", json={"title": "x", "assignee_id": team["outsider"].id}
    )
    assert r.json()["error"]["code"] == "invalid_assignee"
    assert _subtask(client, "TF-999").status_code == 404


def test_member_can_add_subtask(client, team):
    parent = _create(client)
    login(client, team["dev"].email)
    assert _subtask(client, parent["key"]).status_code == 201


def test_outsider_cannot_see_or_add_subtasks(client, team):
    parent = _create(client)
    login(client, team["outsider"].email)
    assert client.get(f"{API}/tasks/{parent['key']}/subtasks").status_code == 404
    assert _subtask(client, parent["key"]).status_code == 404


def test_unauthenticated_subtask_requests_are_rejected(client, team):
    parent = _create(client)
    client.post(f"{API}/auth/logout")
    client.cookies.clear()
    assert client.get(f"{API}/tasks/{parent['key']}/subtasks").status_code == 401

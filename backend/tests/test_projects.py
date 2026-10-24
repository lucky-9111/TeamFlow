import pytest

from app.models.enums import WorkspaceRole
from tests.conftest import login

API = "/api/v1"


@pytest.fixture
def team(client, make_user):
    admin = make_user(role=WorkspaceRole.ADMIN, username="admin")
    dev = make_user(username="dev")
    outsider = make_user(username="outsider")
    login(client, admin.email)
    r = client.post(f"{API}/projects", json={"key": "TF", "name": "TeamFlow"})
    assert r.status_code == 201, r.text
    r = client.post(f"{API}/projects/TF/members", json={"user_id": dev.id, "role": "developer"})
    assert r.status_code == 201, r.text
    return {"admin": admin, "dev": dev, "outsider": outsider}


def test_admin_creates_project_and_becomes_manager(client, team):
    r = client.get(f"{API}/projects/TF")
    assert r.status_code == 200
    body = r.json()
    assert body["key"] == "TF"
    assert body["my_role"] == "manager"
    assert {m["user"]["username"] for m in body["members"]} == {"admin", "dev"}
    assert body["permissions"]["can_manage_members"] is True


def test_project_key_must_be_unique_and_well_formed(client, team):
    assert client.post(f"{API}/projects", json={"key": "TF", "name": "Again"}).status_code == 409
    assert client.post(f"{API}/projects", json={"key": "tf2", "name": "Bad"}).status_code == 422
    assert client.post(f"{API}/projects", json={"key": "X", "name": "Short"}).status_code == 422


def test_project_end_date_cannot_precede_start(client, team):
    r = client.post(
        f"{API}/projects",
        json={"key": "DT", "name": "Dates", "start_date": "2026-05-10", "end_date": "2026-05-01"},
    )
    assert r.status_code == 422


def test_members_cannot_create_projects(client, team):
    login(client, team["dev"].email)
    assert client.post(f"{API}/projects", json={"key": "NO", "name": "Nope"}).status_code == 403


def test_non_members_cannot_see_project(client, team):
    login(client, team["outsider"].email)
    assert client.get(f"{API}/projects").json() == []
    assert client.get(f"{API}/projects/TF").status_code == 404  # 404, not 403: no existence leak


def test_member_sees_project_but_cannot_manage_it(client, team):
    login(client, team["dev"].email)
    body = client.get(f"{API}/projects/TF").json()
    assert body["my_role"] == "developer"
    assert body["permissions"]["can_edit"] is False
    assert client.patch(f"{API}/projects/TF", json={"name": "Hacked"}).status_code == 403
    r = client.post(f"{API}/projects/TF/members", json={"user_id": team["outsider"].id})
    assert r.status_code == 403


def test_last_manager_cannot_be_removed_or_demoted(client, team):
    admin_id = team["admin"].id
    assert client.delete(f"{API}/projects/TF/members/{admin_id}").status_code == 409
    r = client.patch(f"{API}/projects/TF/members/{admin_id}", json={"role": "developer"})
    assert r.status_code == 409


def test_removing_member_unassigns_their_open_tasks(client, team):
    dev = team["dev"]
    task = client.post(f"{API}/projects/TF/tasks", json={"title": "Login page", "assignee_id": dev.id}).json()
    assert client.delete(f"{API}/projects/TF/members/{dev.id}").status_code == 204
    assert client.get(f"{API}/tasks/{task['key']}").json()["assignee"] is None


def test_archived_project_is_read_only(client, team):
    task = client.post(f"{API}/projects/TF/tasks", json={"title": "Before archive"}).json()
    assert client.post(f"{API}/projects/TF/archive").status_code == 200
    assert client.post(f"{API}/projects/TF/tasks", json={"title": "After"}).status_code == 409
    r = client.patch(f"/api/v1/tasks/{task['key']}", json={"version": task["version"], "title": "x"})
    assert r.status_code == 409
    assert client.get(f"{API}/projects").json() == []
    assert len(client.get(f"{API}/projects?include_archived=true").json()) == 1
    assert client.post(f"{API}/projects/TF/unarchive").status_code == 200


def test_member_cannot_create_tasks_when_project_disallows_it(client, team):
    client.patch(f"{API}/projects/TF", json={"members_can_create_tasks": False})
    login(client, team["dev"].email)
    assert client.post(f"{API}/projects/TF/tasks", json={"title": "Mine"}).status_code == 403


def test_adding_member_notifies_them(client, team):
    login(client, team["dev"].email)
    notes = client.get(f"{API}/notifications").json()
    assert notes[0]["type"] == "project_added"
    assert client.get(f"{API}/notifications/unread-count").json() == {"count": 1}
    client.post(f"{API}/notifications/read-all")
    assert client.get(f"{API}/notifications/unread-count").json() == {"count": 0}


class TestTeamManagement:
    def test_admin_creates_member_with_temporary_password(self, client, team):
        r = client.post(
            f"{API}/users",
            json={
                "email": "new@example.com",
                "username": "newbie",
                "full_name": "New Person",
                "temporary_password": "temporary-pass-1",
            },
        )
        assert r.status_code == 201, r.text
        assert "password_hash" not in r.json()
        login(client, "new@example.com", "temporary-pass-1")
        r = client.get(f"{API}/projects")
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "password_change_required"

    def test_members_cannot_manage_users(self, client, team):
        login(client, team["dev"].email)
        assert client.get(f"{API}/users").status_code == 200  # the team list is visible to everyone
        assert client.post(f"{API}/users/{team['outsider'].id}/deactivate").status_code == 403

    def test_deactivated_user_is_signed_out(self, client, team, make_user):
        dev = team["dev"]
        other = make_user(username="other")
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as dev_client:
            login(dev_client, dev.email)
            assert dev_client.get(f"{API}/auth/me").status_code == 200
            assert client.post(f"{API}/users/{dev.id}/deactivate").status_code == 200
            assert dev_client.get(f"{API}/auth/me").status_code == 401
        assert other.is_active

    def test_admin_cannot_deactivate_self_or_last_admin(self, client, team):
        admin_id = team["admin"].id
        assert client.post(f"{API}/users/{admin_id}/deactivate").status_code == 409
        r = client.patch(f"{API}/users/{admin_id}", json={"workspace_role": "member"})
        assert r.status_code == 409

    def test_team_list_shows_projects_and_open_tasks(self, client, team):
        dev = team["dev"]
        client.post(f"{API}/projects/TF/tasks", json={"title": "Work", "assignee_id": dev.id})
        members = {m["username"]: m for m in client.get(f"{API}/users").json()}
        assert members["dev"]["open_task_count"] == 1
        assert members["dev"]["projects"] == [{"key": "TF", "name": "TeamFlow", "role": "developer"}]

    def test_profile_update_validates_timezone(self, client, team):
        assert client.patch(f"{API}/auth/me", json={"timezone": "Mars/Base"}).status_code == 422
        r = client.patch(f"{API}/auth/me", json={"full_name": "Boss", "timezone": "Asia/Kolkata"})
        assert r.status_code == 200
        assert r.json()["timezone"] == "Asia/Kolkata"

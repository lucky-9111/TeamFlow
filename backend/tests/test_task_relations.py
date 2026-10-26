from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models import Notification
from app.models.enums import NotificationType, WorkspaceRole
from app.services.reminders import send_due_reminders
from tests.conftest import login

API = "/api/v1"


@pytest.fixture
def team(client, make_user):
    users = {
        "admin": make_user(role=WorkspaceRole.ADMIN, username="admin"),
        "dev": make_user(username="dev"),
        "dev2": make_user(username="dev2"),
        "outsider": make_user(username="outsider"),
    }
    login(client, users["admin"].email)
    client.post(f"{API}/projects", json={"key": "TF", "name": "TeamFlow"})
    client.post(f"{API}/projects", json={"key": "MOB", "name": "Mobile"})
    for name in ("dev", "dev2"):
        r = client.post(f"{API}/projects/TF/members", json={"user_id": users[name].id, "role": "developer"})
        assert r.status_code == 201
    return users


def _create(client, project="TF", **fields):
    r = client.post(f"{API}/projects/{project}/tasks", json={"title": "Build login", **fields})
    assert r.status_code == 201, r.text
    return r.json()


def _depend(client, task, on):
    return client.post(f"{API}/tasks/{task['key']}/dependencies", json={"depends_on": on["key"]})


def _move(client, task, *statuses):
    for to in statuses:
        r = client.post(
            f"{API}/tasks/{task['key']}/transitions", json={"to_status": to, "version": task["version"]}
        )
        assert r.status_code == 200, r.text
        task = r.json()
    return task


class TestDependencies:
    def test_add_list_and_remove(self, client, team):
        a, b = _create(client, title="API"), _create(client, title="UI")
        r = _depend(client, b, a)
        assert r.status_code == 200
        assert [t["key"] for t in r.json()["depends_on"]] == [a["key"]]
        assert r.json()["unfinished"] == 1
        assert [t["key"] for t in client.get(f"{API}/tasks/{a['key']}/dependencies").json()["blocks"]] == [
            b["key"]
        ]

        _move(client, a, "in_progress", "in_review", "done")
        assert client.get(f"{API}/tasks/{b['key']}/dependencies").json()["unfinished"] == 0

        r = client.delete(f"{API}/tasks/{b['key']}/dependencies/{a['key']}")
        assert r.status_code == 200 and r.json()["depends_on"] == []
        assert client.delete(f"{API}/tasks/{b['key']}/dependencies/{a['key']}").status_code == 404

    def test_adding_twice_is_harmless(self, client, team):
        a, b = _create(client), _create(client)
        _depend(client, b, a)
        assert len(_depend(client, b, a).json()["depends_on"]) == 1

    def test_self_dependency_rejected(self, client, team):
        a = _create(client)
        r = _depend(client, a, a)
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_dependency"

    def test_cycles_rejected(self, client, team):
        a, b, c = _create(client), _create(client), _create(client)
        assert _depend(client, b, a).status_code == 200
        assert _depend(client, c, b).status_code == 200
        r = _depend(client, a, c)  # a -> c -> b -> a
        assert r.status_code == 422 and r.json()["error"]["code"] == "dependency_cycle"
        assert _depend(client, a, b).json()["error"]["code"] == "dependency_cycle"

    def test_other_project_and_unknown_tasks_rejected(self, client, team):
        a, other = _create(client), _create(client, project="MOB")
        assert _depend(client, a, other).json()["error"]["code"] == "invalid_dependency"
        assert (
            client.post(f"{API}/tasks/{a['key']}/dependencies", json={"depends_on": "TF-99"}).status_code
            == 422
        )

    def test_status_changes_are_not_blocked(self, client, team):
        a, b = _create(client), _create(client)
        _depend(client, b, a)
        _move(client, b, "in_progress")

    def test_only_editors_change_dependencies(self, client, team):
        a, b = _create(client), _create(client)
        login(client, team["dev"].email)
        assert client.get(f"{API}/tasks/{b['key']}/dependencies").status_code == 200
        assert _depend(client, b, a).status_code == 403
        login(client, team["outsider"].email)
        assert client.get(f"{API}/tasks/{b['key']}/dependencies").status_code == 404

    def test_deleting_a_task_removes_its_links(self, client, team):
        a, b = _create(client), _create(client)
        _depend(client, b, a)
        assert client.delete(f"{API}/tasks/{a['key']}").status_code == 204
        assert client.get(f"{API}/tasks/{b['key']}/dependencies").json()["depends_on"] == []


class TestLabels:
    def test_add_normalizes_and_ignores_duplicates(self, client, team):
        task = _create(client)
        r = client.post(f"{API}/tasks/{task['key']}/labels", json={"name": "  Front  End "})
        assert r.status_code == 200 and r.json()["labels"] == ["front end"]
        r = client.post(f"{API}/tasks/{task['key']}/labels", json={"name": "FRONT END"})
        assert r.json()["labels"] == ["front end"]
        client.post(f"{API}/tasks/{task['key']}/labels", json={"name": "api"})
        assert client.get(f"{API}/tasks/{task['key']}").json()["labels"] == ["api", "front end"]
        assert client.get(f"{API}/projects/TF/labels").json() == ["api", "front end"]

    def test_invalid_labels_rejected(self, client, team):
        task = _create(client)
        for name in ("", "   ", "x" * 31, "<script>"):
            assert client.post(f"{API}/tasks/{task['key']}/labels", json={"name": name}).status_code == 422

    def test_label_limit(self, client, team):
        task = _create(client)
        for i in range(10):
            client.post(f"{API}/tasks/{task['key']}/labels", json={"name": f"l{i}"})
        r = client.post(f"{API}/tasks/{task['key']}/labels", json={"name": "one-more"})
        assert r.status_code == 422 and r.json()["error"]["code"] == "too_many_labels"

    def test_remove_and_filter(self, client, team):
        task, other = _create(client), _create(client)
        client.post(f"{API}/tasks/{task['key']}/labels", json={"name": "bug"})
        assert [t["key"] for t in client.get(f"{API}/tasks", params={"label": "BUG"}).json()["items"]] == [
            task["key"]
        ]
        r = client.delete(f"{API}/tasks/{task['key']}/labels/bug")
        assert r.status_code == 200 and r.json()["labels"] == []
        assert client.delete(f"{API}/tasks/{task['key']}/labels/bug").status_code == 404
        assert client.get(f"{API}/tasks", params={"label": "bug"}).json()["total"] == 0
        assert other["labels"] == []

    def test_only_editors_change_labels(self, client, team):
        task = _create(client)
        login(client, team["dev"].email)
        assert client.post(f"{API}/tasks/{task['key']}/labels", json={"name": "x"}).status_code == 403
        login(client, team["outsider"].email)
        assert client.post(f"{API}/tasks/{task['key']}/labels", json={"name": "x"}).status_code == 404


class TestWatchers:
    def test_watch_and_unwatch(self, client, team):
        task = _create(client)
        login(client, team["dev"].email)
        r = client.post(f"{API}/tasks/{task['key']}/watch")
        assert r.status_code == 200 and r.json()["watching"] is True
        assert [w["username"] for w in r.json()["watchers"]] == ["dev"]
        assert len(client.post(f"{API}/tasks/{task['key']}/watch").json()["watchers"]) == 1
        r = client.delete(f"{API}/tasks/{task['key']}/watch")
        assert r.json()["watching"] is False and r.json()["watchers"] == []

    def test_outsider_cannot_watch(self, client, team):
        task = _create(client)
        login(client, team["outsider"].email)
        assert client.post(f"{API}/tasks/{task['key']}/watch").status_code == 404

    def test_watchers_get_status_and_comment_updates(self, client, team, db):
        task = _create(client)
        login(client, team["dev"].email)
        client.post(f"{API}/tasks/{task['key']}/watch")
        login(client, team["admin"].email)
        _move(client, task, "in_progress")
        client.post(f"{API}/tasks/{task['key']}/comments", json={"body": "hi"})
        types = db.scalars(
            select(Notification.type).where(
                Notification.recipient_id == team["dev"].id, Notification.task_id == task["id"]
            )
        ).all()
        assert sorted(types) == [NotificationType.TASK_COMMENT, NotificationType.TASK_STATUS]

    def test_removed_member_stops_getting_updates(self, client, team, db):
        task = _create(client)
        login(client, team["dev"].email)
        client.post(f"{API}/tasks/{task['key']}/watch")
        login(client, team["admin"].email)
        assert client.delete(f"{API}/projects/TF/members/{team['dev'].id}").status_code == 204
        _move(client, task, "in_progress")
        mine = select(Notification.id).where(
            Notification.recipient_id == team["dev"].id, Notification.task_id == task["id"]
        )
        assert db.scalar(mine) is None


class TestBulk:
    def test_bulk_priority_and_label(self, client, team):
        a, b = _create(client), _create(client)
        r = client.post(f"{API}/tasks/bulk", json={"task_keys": [a["key"], b["key"]], "priority": "urgent"})
        assert r.status_code == 200 and r.json() == {"updated": [a["key"], b["key"]], "failed": []}
        assert client.get(f"{API}/tasks/{b['key']}").json()["priority"] == "urgent"
        r = client.post(
            f"{API}/tasks/bulk", json={"task_keys": [a["key"], b["key"]], "add_label": "Sprint 1"}
        )
        assert r.json()["failed"] == []
        assert client.get(f"{API}/tasks/{a['key']}").json()["labels"] == ["sprint 1"]

    def test_bulk_assign_and_unassign(self, client, team):
        a, b = _create(client), _create(client)
        keys = [a["key"], b["key"]]
        client.post(f"{API}/tasks/bulk", json={"task_keys": keys, "assignee_id": team["dev"].id})
        assert client.get(f"{API}/tasks/{a['key']}").json()["assignee"]["username"] == "dev"
        client.post(f"{API}/tasks/bulk", json={"task_keys": keys, "assignee_id": None})
        assert client.get(f"{API}/tasks/{a['key']}").json()["assignee"] is None

    def test_partial_failures_are_reported(self, client, team):
        todo = _create(client)
        started = _move(client, _create(client), "in_progress")
        r = client.post(
            f"{API}/tasks/bulk",
            json={"task_keys": [todo["key"], started["key"], "TF-99"], "status": "in_review"},
        )
        body = r.json()
        assert body["updated"] == [started["key"]]
        assert [f["key"] for f in body["failed"]] == [todo["key"], "TF-99"]
        assert client.get(f"{API}/tasks/{todo['key']}").json()["status"] == "todo"

    def test_permissions_apply_per_task(self, client, team):
        mine = _create(client, assignee_id=team["dev"].id)
        other = _create(client)
        hidden = _create(client, project="MOB")
        login(client, team["dev"].email)
        r = client.post(
            f"{API}/tasks/bulk",
            json={"task_keys": [mine["key"], other["key"], hidden["key"]], "priority": "high"},
        )
        assert r.json()["updated"] == [mine["key"]]
        assert {f["key"] for f in r.json()["failed"]} == {other["key"], hidden["key"]}

    def test_request_validation(self, client, team):
        a = _create(client)
        bulk = f"{API}/tasks/bulk"
        assert client.post(bulk, json={"task_keys": [], "priority": "high"}).status_code == 422
        assert client.post(bulk, json={"task_keys": [a["key"]]}).status_code == 422
        assert (
            client.post(
                bulk, json={"task_keys": [a["key"]], "priority": "high", "status": "done"}
            ).status_code
            == 422
        )
        assert client.post(bulk, json={"task_keys": [a["key"]], "priority": None}).status_code == 422
        assert client.post(bulk, json={"task_keys": ["X-1"] * 101, "priority": "high"}).status_code == 422


class TestReminders:
    def test_reminds_assignee_and_watchers_once(self, client, team, db):
        today = date.today()
        due = _create(client, assignee_id=team["dev"].id, due_date=str(today + timedelta(days=1)))
        _create(client, assignee_id=team["dev"].id, due_date=str(today + timedelta(days=5)))
        login(client, team["dev2"].email)
        client.post(f"{API}/tasks/{due['key']}/watch")

        assert send_due_reminders(db, today) == 1
        assert send_due_reminders(db, today) == 0  # re-running never duplicates
        rows = db.scalars(select(Notification).where(Notification.type == NotificationType.TASK_DUE)).all()
        assert sorted(n.recipient_id for n in rows) == sorted([team["dev"].id, team["dev2"].id])
        assert rows[0].message == f"{due['key']} is due tomorrow: Build login"

    def test_skips_done_tasks_and_opted_out_users(self, client, team, db):
        today = date.today()
        done = _create(client, assignee_id=team["admin"].id, due_date=str(today))
        _move(client, done, "in_progress", "in_review", "done")
        _create(client, assignee_id=team["dev"].id, due_date=str(today))
        login(client, team["dev"].email)
        r = client.patch(f"{API}/auth/me", json={"due_reminders": False})
        assert r.status_code == 200 and r.json()["due_reminders"] is False
        db.expire_all()  # the API changed the preference in another session

        assert send_due_reminders(db, today) == 1
        assert (
            db.scalar(select(Notification.id).where(Notification.type == NotificationType.TASK_DUE)) is None
        )

    def test_new_due_date_gets_a_new_reminder(self, client, team, db):
        today = date.today()
        task = _create(client, assignee_id=team["dev"].id, due_date=str(today))
        assert send_due_reminders(db, today) == 1
        client.patch(
            f"{API}/tasks/{task['key']}",
            json={"version": task["version"], "due_date": str(today + timedelta(days=1))},
        )
        assert send_due_reminders(db, today) == 1

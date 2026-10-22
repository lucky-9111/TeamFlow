from datetime import timedelta

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.main import app
from app.models import AuthSession
from app.models.base import utcnow
from tests.conftest import DEFAULT_PASSWORD, login

# A protected endpoint used to exercise the auth dependencies until real ones exist (Phase 3).
_probe = APIRouter()


@_probe.get("/api/v1/_test/protected")
def _protected_get(user: CurrentUser):
    return {"id": user.id}


@_probe.post("/api/v1/_test/protected")
def _protected_post(user: CurrentUser):
    return {"id": user.id}


app.include_router(_probe)


def test_login_sets_secure_cookies_and_returns_safe_user(client, make_user):
    user = make_user()
    response = login(client, user.email)
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == user.email
    assert "password_hash" not in body["user"]
    assert body["csrf_token"]

    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("teamflow_session="))
    csrf_cookie = next(c for c in cookies if c.startswith("teamflow_csrf="))
    assert "HttpOnly" in session_cookie and "samesite=lax" in session_cookie.lower()
    assert "HttpOnly" not in csrf_cookie


def test_session_token_is_stored_hashed(client, make_user, db):
    user = make_user()
    login(client, user.email)
    token = client.cookies.get("teamflow_session")
    stored = db.scalars(select(AuthSession.token_hash)).all()
    assert token not in stored and len(stored) == 1


def test_login_email_is_case_insensitive(client, make_user):
    user = make_user()
    assert login(client, user.email.upper()).status_code == 200


def test_wrong_password_and_unknown_email_get_the_same_error(client, make_user):
    user = make_user()
    wrong = login(client, user.email, "not-the-password")
    unknown = login(client, "nobody@example.com", "whatever-password")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["code"] == "invalid_credentials"


def test_inactive_user_cannot_log_in(client, make_user):
    user = make_user(is_active=False)
    assert login(client, user.email).status_code == 401


def test_login_rejects_unknown_fields(client, make_user):
    user = make_user()
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD, "role": "admin"}
    )
    assert response.status_code == 422
    assert DEFAULT_PASSWORD not in response.text  # submitted values are never echoed back


def test_me_requires_authentication(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_returns_current_user(client, make_user):
    user = make_user()
    login(client, user.email)
    assert client.get("/api/v1/auth/me").json()["id"] == user.id


def test_logout_invalidates_session_server_side(client, make_user):
    user = make_user()
    login(client, user.email)
    stolen_cookie = client.cookies.get("teamflow_session")

    assert client.post("/api/v1/auth/logout").status_code == 204

    # Even if the old cookie is replayed, the server-side session is revoked.
    client.cookies.set("teamflow_session", stolen_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_unsafe_requests_require_csrf_token(client, make_user):
    user = make_user()
    login(client, user.email)
    good = client.headers.pop("X-CSRF-Token")

    missing = client.post("/api/v1/_test/protected")
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_failed"

    assert client.post("/api/v1/_test/protected", headers={"X-CSRF-Token": "forged"}).status_code == 403
    assert client.post("/api/v1/_test/protected", headers={"X-CSRF-Token": good}).status_code == 200


def test_csrf_token_is_bound_to_the_session(client, make_user):
    alice, bob = make_user(), make_user()
    alice_csrf = login(client, alice.email).json()["csrf_token"]
    login(client, bob.email)
    response = client.post("/api/v1/_test/protected", headers={"X-CSRF-Token": alice_csrf})
    assert response.status_code == 403


def test_csrf_refresh_rotates_token(client, make_user):
    user = make_user()
    old = login(client, user.email).json()["csrf_token"]
    new = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    assert new != old
    assert client.post("/api/v1/_test/protected", headers={"X-CSRF-Token": old}).status_code == 403
    assert client.post("/api/v1/_test/protected", headers={"X-CSRF-Token": new}).status_code == 200


def test_idle_session_expires(client, make_user, db):
    user = make_user()
    login(client, user.email)
    session = db.scalar(select(AuthSession))
    session.last_seen_at = utcnow() - timedelta(hours=13)
    db.commit()

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"


def test_absolute_session_lifetime_expires(client, make_user, db):
    user = make_user()
    login(client, user.email)
    session = db.scalar(select(AuthSession))
    session.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_deactivated_user_session_stops_working(client, make_user, db):
    user = make_user()
    login(client, user.email)
    user.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_repeated_failures_lock_the_account_temporarily(client, make_user):
    user = make_user()
    for _ in range(5):
        assert login(client, user.email, "wrong-password").status_code == 401
    # Locked even with the correct password.
    response = login(client, user.email)
    assert response.status_code == 429


def test_successful_login_resets_failure_count(client, make_user):
    user = make_user()
    for _ in range(4):
        login(client, user.email, "wrong-password")
    assert login(client, user.email).status_code == 200
    for _ in range(4):
        login(client, user.email, "wrong-password")
    assert login(client, user.email).status_code == 200


def test_change_password_flow(client, make_user):
    user = make_user()
    login(client, user.email)

    bad = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "wrong-password", "new_password": "a-brand-new-password"},
    )
    assert bad.status_code == 422

    too_short = client.post(
        "/api/v1/auth/change-password", json={"current_password": DEFAULT_PASSWORD, "new_password": "short"}
    )
    assert too_short.status_code == 422

    ok = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "a-brand-new-password"},
    )
    assert ok.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 200  # current session survives

    client.cookies.clear()
    assert login(client, user.email).status_code == 401
    assert login(client, user.email, "a-brand-new-password").status_code == 200


def test_change_password_signs_out_other_sessions(client, make_user, db):
    from fastapi.testclient import TestClient

    user = make_user()
    with TestClient(app) as other_device:
        login(other_device, user.email)
        login(client, user.email)
        client.post(
            "/api/v1/auth/change-password",
            json={"current_password": DEFAULT_PASSWORD, "new_password": "a-brand-new-password"},
        )
        assert other_device.get("/api/v1/auth/me").status_code == 401
        assert client.get("/api/v1/auth/me").status_code == 200


def test_temporary_password_must_be_changed_first(client, make_user):
    user = make_user(must_change_password=True)
    login(client, user.email)

    assert client.get("/api/v1/auth/me").json()["must_change_password"] is True
    blocked = client.get("/api/v1/_test/protected")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"

    client.post(
        "/api/v1/auth/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "a-brand-new-password"},
    )
    assert client.get("/api/v1/_test/protected").status_code == 200


def test_api_responses_carry_security_headers(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"

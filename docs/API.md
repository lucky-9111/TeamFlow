# TeamFlow API (v1)

Base path: `/api/v1`. Interactive docs with request/response schemas: http://127.0.0.1:8000/api/docs
(development only).

## Conventions

- **Auth:** an HttpOnly session cookie set by `POST /auth/login`. Every request except login and
  `/health` needs it.
- **CSRF:** every `POST`/`PATCH`/`DELETE` must send the `teamflow_csrf` cookie value in the
  `X-CSRF-Token` header. `GET /auth/csrf` issues a fresh token.
- **Errors** always look like `{"error": {"code": "...", "message": "...", "details": ...}}`.

  | Status | Meaning | Typical codes |
  |--------|---------|---------------|
  | 400 | Request is understood but not allowed by the workflow | `invalid_transition` |
  | 401 | Not signed in / session expired | `not_authenticated`, `session_expired`, `invalid_credentials` |
  | 403 | Signed in, but not allowed | `forbidden`, `csrf_failed`, `password_change_required` |
  | 404 | Doesn't exist **or you can't see it** (non-members get 404, not 403) | `not_found` |
  | 409 | Conflicts with the current state | `stale_version`, `project_archived`, `last_admin`, `last_manager`, `project_key_taken` |
  | 422 | Invalid input | `validation_error`, `invalid_assignee` |
  | 429 | Too many failed logins | `too_many_requests` |

- **Lists** that can grow return `{items, total, page, page_size}`; `page_size` is capped at 100.
- **Concurrency:** tasks carry a `version`. `PATCH /tasks/{key}` and transitions must send the
  version they loaded; if someone else changed the task first, the API answers `409 stale_version`.
- Dates are `YYYY-MM-DD`; timestamps are ISO 8601 in UTC.

## Auth & profile

| Method | Path | Notes |
|--------|------|-------|
| POST | `/auth/login` | `{email, password}` → `{user, csrf_token}` and cookies |
| POST | `/auth/logout` | Revokes the session |
| GET | `/auth/me` | Current user |
| PATCH | `/auth/me` | `{full_name?, timezone?}` |
| POST | `/auth/change-password` | `{current_password, new_password}`; signs out other devices |
| GET | `/auth/csrf` | New CSRF token for the current session |

## Team & workspace

| Method | Path | Who | Notes |
|--------|------|-----|-------|
| GET | `/users?q=&include_inactive=` | everyone | Team list with open task counts and project roles |
| POST | `/users` | admin | `{email, username, full_name, workspace_role, temporary_password}` |
| PATCH | `/users/{id}` | admin | `{full_name?, workspace_role?}`; the last admin can't be demoted |
| POST | `/users/{id}/deactivate` | admin | Signs them out; can't deactivate yourself or the last admin |
| POST | `/users/{id}/activate` | admin | |
| POST | `/users/{id}/reset-password` | admin | `{temporary_password}`; they must change it at next login |
| GET | `/workspace` | everyone | `{name}` |
| PATCH | `/workspace` | admin | `{name}` |

## Projects

`{key}` is the project key, e.g. `TF`. Non-members get 404.

| Method | Path | Who | Notes |
|--------|------|-----|-------|
| GET | `/projects?include_archived=` | members (admins: all) | With task counts, member count and your role |
| POST | `/projects` | admin | `{key, name, description?, status?, start_date?, end_date?, members_can_create_tasks?}`; creator becomes manager |
| GET | `/projects/{key}` | members | Detail + members + `permissions` flags for the UI |
| PATCH | `/projects/{key}` | manager/admin | Partial update; the key never changes |
| POST | `/projects/{key}/archive` · `/unarchive` | admin | Archived projects are read-only |
| GET | `/projects/{key}/members` | members | |
| POST | `/projects/{key}/members` | manager/admin | `{user_id, role}` (manager/developer/tester/designer) |
| PATCH | `/projects/{key}/members/{user_id}` | manager/admin | `{role}`; a project keeps at least one manager |
| DELETE | `/projects/{key}/members/{user_id}` | manager/admin | Their open tasks become unassigned |
| GET | `/projects/{key}/board?assignee=&q=&priority=&type=` | members | Tasks grouped by status, each with `allowed_transitions` for you |
| POST | `/projects/{key}/tasks` | members (see project setting) | `{title, description?, type?, priority?, assignee_id?, start_date?, due_date?}` |

## Tasks

`{task_key}` is e.g. `TF-12`. Numbers are per project and never reused.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/tasks` | Filters: `project`, `status` (repeatable), `priority`, `type`, `assignee` (`me`, `none` or a user id), `q` (title or key), `overdue`; `sort` = `updated`/`created`/`due`/`priority`/`status`/`key`, `order` = `asc`/`desc`, `page`, `page_size` |
| GET | `/tasks/{task_key}` | Detail with `allowed_transitions` and `permissions` |
| PATCH | `/tasks/{task_key}` | `{version, title?, description?, type?, priority?, assignee_id?, start_date?, due_date?}`. Cannot change status. |
| POST | `/tasks/{task_key}/transitions` | `{to_status, version}`. See the workflow in the README. |
| DELETE | `/tasks/{task_key}` | Managers/admins |
| GET | `/tasks/{task_key}/activity` | History of this task |
| GET | `/tasks/{task_key}/comments` | |
| POST | `/tasks/{task_key}/comments` | `{body}` |
| PATCH | `/comments/{id}` | Author, or a project manager |
| DELETE | `/comments/{id}` | Author, or a project manager |

## Overview

| Method | Path | Notes |
|--------|------|-------|
| GET | `/dashboard` | Counts, my tasks, upcoming deadlines (14 days), recently completed, recent activity, project progress |
| GET | `/activity?project=&page=&page_size=` | Activity feed for projects you can see (admins also see team changes) |
| GET | `/search?q=` | Up to 5 projects and 10 tasks |
| GET | `/notifications?unread=&limit=` | Newest first |
| GET | `/notifications/unread-count` | `{count}` |
| POST | `/notifications/{id}/read` · `/notifications/read-all` | |
| GET | `/health` | No auth. `{"status": "ok"}` |

Notifications are created when someone else assigns you a task, moves or comments on a task you
reported or are assigned to, or adds you to a project.

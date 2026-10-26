# TeamFlow — Architecture & Implementation Plan

Internal, single-workspace project management tool (Jira-inspired) for a ~10 person team.
This document is the Phase 1 deliverable and the reference for later phases. Update it when a
decision changes.

## 0. Implementation status (updated 2026-10-22)

Built and tested: auth, team management, workspace settings, projects + members + archive, tasks
(keys like `TF-12`), workflow transitions, comments, activity history, in-app notifications,
dashboard, search, and the React frontend (Overview, My Tasks/task list, Projects, Board with
drag-and-drop, Task detail, Team, Activity, Settings). See [API.md](API.md) for the endpoints that exist.

**Next phase, Phase 1 (2026-10-26):** subtasks (`tasks.parent_id`, one level), task dependencies
(`task_dependencies`), labels (`task_labels`), watchers (`task_watchers`), bulk updates
(`POST /tasks/bulk`) and due-date reminders (`task_reminders` + `python -m app.cli send-due-reminders`).
The rows below about hierarchy, links, labels and reminders describe v1 and are superseded by this.
See [AUDIT.md](AUDIT.md) for the feature matrix and the Phase 1 report.

Deliberate differences from the original plan below, to keep v1 small for a 2–10 person team:

| Plan | What was built | Why |
|------|----------------|-----|
| "Issues" with Epic/Story/Task/Bug/Subtask, hierarchy, links, labels | "Tasks" with type Task / Story / Bug, no hierarchy, links or labels | The product brief asks for simple tasks; hierarchy can be added later without breaking keys |
| Sprints, backlog ranking, story points, work logs, burndown reports | Not built | Out of scope for v1; the board + list + dashboard cover daily use |
| Attachments | Not built | Not in the v1 brief; `TEAMFLOW_UPLOAD_DIR` is reserved for it |
| Only managers create Epic/Story/Task; developers create bugs | Every project member can create tasks; a per-project switch (`members_can_create_tasks`) limits it to managers | Matches "create tasks if permitted by the project" |
| `issue_history` + `audit_events` tables | One `activity_events` table (project and/or task scoped; team events have no project) | One feed, one query |
| Board columns from sprints | Board shows every task of the project (max 500), filterable | No sprints in v1 |
| Deadline reminder CLI, mentions | Not built | Notifications cover assignment, status changes, comments and being added to a project |

Next candidates if the team needs them: attachments, @mentions, deadline reminders, sprints,
deployment files (Nginx/systemd, backups), CI workflow.

## 1. Environment (inspected 2026-10-20)

| Tool    | Found                    | Decision |
|---------|--------------------------|----------|
| Python  | 3.14.0a7 (default), 3.13 | Use **3.13** for the backend venv; 3.14 alpha lacks wheels for pydantic-core etc. CI pins 3.13. |
| Node    | 24.21 / npm 11.19        | OK for Vite + React. CI pins Node 22 LTS or 24. |
| Git     | 2.55                     | Repo `lucky-9111/TeamFlow`, branch `main`. |
| Docker  | not installed            | Dockerfiles are written in Phase 8 and verified by CI `docker build`. |

## 2. Architecture overview

```
Browser (React SPA)
   │  same-origin /api/*  (HttpOnly session cookie + CSRF header)
   ▼
Nginx ── serves frontend/dist static files
   │  proxy_pass /api → 127.0.0.1:8000
   ▼
Uvicorn + FastAPI (single process, sync SQLAlchemy)
   ├── routes → services (business rules, permissions) → repositories → SQLAlchemy models
   ├── SQLite (WAL, foreign_keys=ON, busy_timeout) — data/teamflow.db
   └── Upload storage on disk — data/uploads/ (outside any public dir)
Cron / systemd timer → `python -m app.cli send-deadline-reminders`, `backup-db`
```

Key choices:

- **Monolith, no microservices.** One FastAPI app, one SQLite file, one upload directory.
- **Sync SQLAlchemy 2.x** (not async). SQLite gains nothing from async; sync is simpler to test and
  FastAPI runs sync endpoints in a threadpool. Switching to PostgreSQL later means changing
  `DATABASE_URL` plus the SQLite-only pragmas in `core/database.py`.
- **Backend is authoritative.** The frontend never decides permissions or valid transitions; it
  asks the API (`/issues/{key}` returns `allowed_transitions` and `permissions` flags for UI hints).
- **Same-origin deployment.** In dev, Vite proxies `/api` to FastAPI, so cookies work with no CORS.

### Authentication design

- **Server-side sessions** stored in `auth_sessions`. The browser holds an opaque random token
  (`secrets.token_urlsafe(32)`) in a cookie: `HttpOnly; Secure (prod); SameSite=Lax; Path=/`.
  Only the SHA-256 of the token is stored in the DB.
- **Expiry:** idle timeout (default 12 h, sliding) + absolute lifetime (default 7 days). Logout
  revokes the session row immediately; a password change revokes all of the user's *other*
  sessions (the current one stays signed in); deactivating a user revokes all sessions.
- **Temporary passwords:** while `must_change_password` is set, only `/auth/me`, `/auth/logout`,
  `/auth/csrf` and `/auth/change-password` work; everything else returns 403 `password_change_required`.
- **CSRF:** double-submit token. A non-HttpOnly `csrf_token` cookie is issued at login; every
  unsafe request (POST/PUT/PATCH/DELETE) must send it back in `X-CSRF-Token`, and the server checks
  it against the value bound to the session. Combined with SameSite=Lax.
- **Passwords:** Argon2id via `argon2-cffi`. Minimum length 10, checked server-side.
- **Login throttling:** simple per-account + per-IP failed-attempt counter (in DB) with temporary lockout.
- **Initial admin:** no public registration. `python -m app.cli create-admin` (interactive / env
  vars) creates the first Workspace Admin and refuses if an admin already exists.
- **Members:** an admin creates members with a temporary password and `must_change_password=True`.
  Email invitations come later, behind a configurable mail integration.

### Roles & permissions

Two layers:

1. **Workspace role** on the user: `admin` | `member`.
2. **Project role** on `project_members`: `manager` | `developer` | `tester` | `designer`.
   One user can hold different roles in different projects. Admins have implicit access to every project.

All checks live in `core/permissions.py` as named actions (`issue.create`, `issue.transition`,
`sprint.manage`, ...) and are evaluated in services. Routes never inline role logic.

| Action                                        | Admin | Manager | Developer | Tester | Designer |
|-----------------------------------------------|:-----:|:-------:|:---------:|:------:|:--------:|
| Manage users, workspace settings              | ✔ | – | – | – | – |
| Create / archive projects                     | ✔ | – | – | – | – |
| Edit project, manage project members          | ✔ | ✔ | – | – | – |
| View project & its issues                     | ✔ | ✔ | ✔ | ✔ | ✔ |
| Create Epic / Story / Task                    | ✔ | ✔ | – | – | – |
| Create Bug                                    | ✔ | ✔ | ✔ (project setting, default on) | ✔ | – |
| Create Subtask under an issue they can edit   | ✔ | ✔ | ✔ | ✔ | ✔ |
| Edit any issue field, assign anyone           | ✔ | ✔ | – | – | – |
| Edit own assigned issue (description, estimate, dates, labels) | ✔ | ✔ | ✔ | ✔ | ✔ |
| Edit bugs (any field except assignee to others)| ✔ | ✔ | – | ✔ | – |
| Transition status                             | any | any | own assigned, up to In Review | bugs + issues In Review | own assigned, up to In Review |
| Move In Review → Done                         | ✔ | ✔ | – | ✔ | – |
| Reopen Done → In Progress                     | ✔ | ✔ | – | ✔ | – |
| Comment, attach files                         | ✔ | ✔ | ✔ | ✔ | ✔ |
| Log work on an issue                          | ✔ | ✔ | ✔ | ✔ | ✔ |
| Edit/delete own comment, worklog, attachment  | ✔ | ✔ | ✔ | ✔ | ✔ |
| Delete others' comments / attachments         | ✔ | ✔ | – | – | – |
| Manage sprints & backlog order                | ✔ | ✔ | – | – | – |
| Delete issue (no children)                    | ✔ | ✔ | – | – | – |
| Project reports                               | ✔ | ✔ | ✔ (view) | ✔ (view) | ✔ (view) |

Project access is checked on every issue/sprint/attachment lookup (the issue is loaded and its project
membership verified). This is what prevents IDOR: knowing an ID or key is never enough.

### Workflow

Statuses: `todo`, `in_progress`, `in_review`, `done`. Transitions are defined in `services/workflow.py`:

```
todo        → in_progress
in_progress → todo, in_review
in_review   → in_progress (changes requested), done
done        → in_progress (reopen, restricted)
```

`PATCH /issues/{key}` **cannot** change `status`; status changes only go through
`POST /issues/{key}/transitions` which validates both the transition and the role. Setting `done`
stamps `resolved_at`, reopening clears it. Workflow config is code for v1; it can move to DB tables
later without changing the API.

### Issue keys (concurrency-safe)

`projects.next_issue_number` is incremented atomically inside the issue-creation transaction:

```sql
UPDATE projects SET next_issue_number = next_issue_number + 1
WHERE id = :pid RETURNING next_issue_number - 1;
```

SQLite serializes writers, PostgreSQL row-locks the row, so two concurrent creates can never get
the same number. A `UNIQUE(project_id, number)` constraint is the backstop. Project keys are
immutable once the project has issues.

### Concurrent edits

`issues.version` is an SQLAlchemy `version_id_col`. Clients send the `version` they loaded; a stale
update returns **409 Conflict**, and the UI refetches. This also covers the board's optimistic drag.

## 3. Folder structure

```
TeamFlow/
├── backend/
│   ├── app/
│   │   ├── main.py              # app factory, router mounting, error handlers
│   │   ├── cli.py               # create-admin, seed-dev, send-deadline-reminders, backup-db
│   │   ├── core/                # config.py, security.py, permissions.py, database.py, errors.py, logging.py
│   │   ├── models/              # one module per aggregate (user, project, issue, sprint, ...)
│   │   ├── schemas/             # Pydantic in/out models (explicit fields → no mass assignment)
│   │   ├── repositories/        # focused query functions (filters, pagination)
│   │   ├── services/            # business rules: issues, workflow, sprints, notifications, reports
│   │   ├── api/
│   │   │   ├── deps.py          # get_db, get_current_user, require_csrf, project access helpers
│   │   │   └── routes/          # auth, users, workspace, projects, issues, comments, sprints, ...
│   │   └── storage/             # attachment storage backend (local disk; S3 later)
│   ├── alembic/ + alembic.ini
│   ├── tests/                   # pytest; temp-dir SQLite per test session
│   ├── requirements.txt / requirements-dev.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/                 # router, providers (QueryClient, auth, toasts)
│   │   ├── components/          # Button, Dialog, FormField, Table, Badge, Avatar, Skeleton, EmptyState...
│   │   ├── layouts/             # AppShell (sidebar + top bar), AuthLayout
│   │   ├── pages/               # route-level screens
│   │   ├── features/            # auth, workspace, projects, issues, board, sprints, notifications, reports
│   │   ├── services/            # api client (fetch wrapper, CSRF header, error mapping)
│   │   ├── hooks/ types/ utils/
│   ├── index.html, vite.config.ts, tsconfig.json, package.json
├── deploy/                      # nginx.conf, teamflow.service, backup timer, Dockerfiles, compose.yaml
├── docs/                        # ARCHITECTURE.md, DEVELOPMENT.md, DEPLOYMENT.md, BACKUP.md
└── .github/workflows/ci.yml
```

## 4. Database relationships

All timestamps are timezone-aware UTC (`DateTime(timezone=True)`), and the frontend converts them
to local time. Users, projects and issues with history are never hard-deleted from the UI: users are
deactivated, projects are archived. FKs from history tables to `users` use `ON DELETE RESTRICT`.

```
users ─┬─< auth_sessions
       ├─< project_members >── projects ─┬─< issues ─┬─< issue_comments
       │                                 │           ├─< issue_history
       │                                 │           ├─< attachments
       │                                 │           ├─< work_logs
       │                                 │           ├─< issue_labels >── labels (per project)
       │                                 │           ├─< issue_links (source/target → issues)
       │                                 │           └── parent_id → issues (self)
       │                                 ├─< sprints ─< sprint_issues >── issues
       │                                 └─< labels
       ├─< notifications
       └─< audit_events (workspace/project admin actions)
workspace (single row: name, settings)
```

| Table | Key columns & constraints |
|-------|---------------------------|
| `workspace` | id, name, settings JSON. Exactly one row for now. A `workspace_members` table is not needed while there is one workspace; the workspace role lives on `users`. Adding multi-workspace later = new table + migration. |
| `users` | email UNIQUE, username UNIQUE (for @mentions), full_name, password_hash, workspace_role, is_active, must_change_password, timezone, last_login_at |
| `auth_sessions` | token_hash UNIQUE, user_id FK CASCADE, csrf_hash, created_at, last_seen_at, expires_at, revoked_at, ip, user_agent |
| `login_attempts` | identifier, ip, created_at, success (for throttling) |
| `projects` | key UNIQUE (2–10 uppercase), name, description, owner_id FK RESTRICT, status (active/on_hold/completed), archived_at, start_date, end_date, next_issue_number, allow_developer_bugs |
| `project_members` | UNIQUE(project_id, user_id), role |
| `issues` | UNIQUE(project_id, number); type, status, priority, title, description, reporter_id, assignee_id (SET NULL), parent_id (self, RESTRICT), sprint_id (SET NULL), start_date, due_date, story_points, original_estimate_minutes, rank (board/backlog order), resolved_at, version. Indexes: (project_id, status), assignee_id, due_date, sprint_id, parent_id |
| `issue_links` | source_id, target_id, link_type (blocks/relates_to/duplicates); UNIQUE(source, target, type); CHECK source≠target |
| `labels` / `issue_labels` | UNIQUE(project_id, name); PK(issue_id, label_id) |
| `issue_comments` | issue_id CASCADE, author_id RESTRICT, body, edited_at, deleted_at (soft delete keeps thread intact) |
| `issue_history` | issue_id CASCADE, actor_id, action, field, old_value, new_value (JSON-safe text), created_at |
| `sprints` | project_id, name, goal, state (planned/active/completed), start_date, end_date, started_at, completed_at. At most one active sprint per project (enforced in service + partial unique index) |
| `sprint_issues` | sprint_id, issue_id, added_at, removed_at, outcome (completed/carried_over/removed). Membership history for reports; `issues.sprint_id` is the current-sprint pointer |
| `attachments` | issue_id CASCADE, uploader_id, original_name, stored_name (UUID), content_type, size_bytes, sha256 |
| `work_logs` | issue_id CASCADE, user_id RESTRICT, minutes (1–1440), work_date, description |
| `notifications` | recipient_id, actor_id, type, project_id, issue_id, message, read_at, dedupe_key; UNIQUE(recipient_id, dedupe_key) |
| `audit_events` | actor_id, action, entity_type, entity_id, details JSON, created_at |

**Issue hierarchy rules** (service-enforced): Epic has no parent; Story/Task/Bug may have an Epic parent;
Subtask must have a Story/Task/Bug parent; parent and child in the same project; no cycles.

**Sprint completion rule:** completing a sprint requires choosing where *unfinished* issues go:
the backlog (default) or a named planned sprint. Done issues stay recorded with outcome `completed`,
moved issues get `carried_over`. Nothing is silently dropped.

**SQLite settings** (applied on every connection): `PRAGMA foreign_keys=ON`, `journal_mode=WAL`,
`busy_timeout=5000`, `synchronous=NORMAL`.

Every transaction starts with `BEGIN IMMEDIATE`, which takes the write lock up front. That prevents
`SQLITE_BUSY` errors that would otherwise happen when a read transaction upgrades to a write while
another writer commits. The cost is that transactions are serialized, so **never hold a DB session open
across slow work** (e.g. write uploaded files to disk before or after the transaction, not inside it).
Alembic runs with `foreign_keys=OFF` (batch table rebuilds would otherwise fire `ON DELETE CASCADE`)
and finishes with `PRAGMA foreign_key_check`, failing the migration on any violation.

## 5. API endpoints (`/api/v1`)

Lists return `{items, total, page, page_size}`. Errors return `{error: {code, message, details}}`.

**Auth:** `POST /auth/login` · `POST /auth/logout` · `GET /auth/me` · `POST /auth/change-password` · `GET /auth/csrf`

**Workspace & users (admin):** `GET/PATCH /workspace` · `GET /users?q=&role=&active=` · `POST /users` ·
`GET/PATCH /users/{id}` · `POST /users/{id}/deactivate` · `POST /users/{id}/activate` ·
`POST /users/{id}/reset-password` · `GET /users/{id}/projects`

**Projects:** `GET/POST /projects` · `GET/PATCH /projects/{key}` · `POST /projects/{key}/archive` · `POST /projects/{key}/unarchive` ·
`GET/POST /projects/{key}/members` · `PATCH/DELETE /projects/{key}/members/{user_id}` · `GET /projects/{key}/summary`

**Issues:** `GET /issues?project=&status=&assignee=&priority=&type=&due_before=&due_after=&q=&sprint=&page=` ·
`POST /projects/{key}/issues` · `GET/PATCH/DELETE /issues/{issue_key}` · `POST /issues/{issue_key}/transitions` ·
`POST /issues/{issue_key}/rank` (board/backlog reorder) · `GET /issues/{issue_key}/children` ·
`GET/POST /issues/{issue_key}/links` · `DELETE /issue-links/{id}` · `GET /issues/{issue_key}/history`

**Labels:** `GET/POST /projects/{key}/labels` · `PATCH/DELETE /labels/{id}`

**Comments:** `GET/POST /issues/{issue_key}/comments` · `PATCH/DELETE /comments/{id}`

**Board & backlog:** `GET /projects/{key}/board?sprint=active&assignee=&priority=&q=` · `GET /projects/{key}/backlog`

**Sprints:** `GET/POST /projects/{key}/sprints` · `GET/PATCH/DELETE /sprints/{id}` · `POST /sprints/{id}/start` ·
`POST /sprints/{id}/complete` · `POST /sprints/{id}/issues` · `DELETE /sprints/{id}/issues/{issue_key}`

**Attachments:** `GET/POST /issues/{issue_key}/attachments` · `GET /attachments/{id}/download` · `DELETE /attachments/{id}`

**Work logs:** `GET/POST /issues/{issue_key}/worklogs` · `PATCH/DELETE /worklogs/{id}`

**Notifications:** `GET /notifications?unread=` · `GET /notifications/unread-count` · `POST /notifications/{id}/read` · `POST /notifications/read-all`

**Dashboards & reports:** `GET /dashboard` (workspace + my work) · `GET /me/issues` · `GET /activity?project=` ·
`GET /projects/{key}/reports/overview` · `GET /sprints/{id}/reports/burndown` · `GET /sprints/{id}/reports/completion` ·
`GET /projects/{key}/reports/workload`

**Health:** `GET /health` (no auth; DB check, no sensitive details)

## 6. Frontend stack

- React 18 + Vite + **TypeScript**, React Router 6.
- **TanStack Query**: server-state cache. One cache keeps board, issue detail and lists in sync (shared query keys + invalidation), and it gives optimistic updates with rollback for drag-and-drop.
- **dnd-kit**: Kanban drag-and-drop (accessible, maintained).
- **Recharts**: reports and burndown.
- **Tailwind CSS** + **Radix UI primitives** (Dialog, DropdownMenu, Popover, Toast, Select): accessible building blocks wrapped in our own `components/`.
- **react-hook-form + zod**: forms (client validation is UX only; the server re-validates).
- Tests: **Vitest + Testing Library**, with MSW only inside tests.

## 7. Implementation phases & checklist

Each phase ends with: changed-file list, test run, start commands, known gaps, regression check.

- [x] **Phase 1:** environment inspection, this document.
- [x] **Phase 2:** backend skeleton, config (pydantic-settings, dev/prod/test), DB + pragmas, Alembic baseline, User/Session/Workspace models, Argon2, login/logout/me/change-password, CSRF, throttling, `create-admin` CLI, permission framework, error format, pytest setup with an isolated temp DB.
- [x] **Phase 3:** user management (admin), workspace settings, projects CRUD/archive, project members, audit events. Tests for role enforcement and IDOR.
- [x] **Phase 4 (reduced):** tasks (types, keys), workflow transitions, comments, history, filters + pagination. Hierarchy, labels and links deferred (see section 0).
- [x] **Phase 5:** React app shell, API client, auth flow, projects list/overview, issue detail, Kanban board (dnd-kit + optimistic rollback), toasts, skeletons, empty and error states.
- [ ] **Phase 6 (partly done):** global search, filters UI, notifications (assign, status, comment, project added), dashboard and My Tasks are done. Backlog ranking, sprints, mentions and the deadline CLI are not.
- [ ] **Phase 7:** attachments (validation, storage, authorized download), work logs, reports (status/priority/workload, burndown, sprint completion).
- [ ] **Phase 8:** test coverage gaps, frontend tests, security review, Dockerfiles + compose, GitHub Actions (pytest, ruff, tsc, vitest, vite build, docker build), Nginx + systemd config, HTTPS (certbot) guide, backup/restore scripts, deployment checklist.

## 8. Trade-offs & assumptions

1. **SQLite concurrency:** fine for 10 users with WAL; writes are serialized. Run one Uvicorn process (2 at most). PostgreSQL is the upgrade path; no SQLite-specific SQL outside `core/database.py`, and `RETURNING` works on both.
2. **Workflow is fixed in code** (4 statuses). Custom per-project workflows are a later feature.
3. **No email in v1.** Members get temporary passwords from the admin. Notifications are in-app; deadline reminders are produced by a CLI job (cron/systemd timer) and deduplicated by `(recipient, dedupe_key)`.
4. **Bug creation by developers** is a per-project setting, on by default.
5. **Attachments:** max 10 MB (configurable). Allowlist: images, PDF, text/markdown/CSV, Office docs, zip. Executables and HTML/SVG are rejected (SVG can carry scripts). Downloads are always `Content-Disposition: attachment` with `nosniff`.
6. **Estimates:** story points (optional) for sprint planning and burndown, plus original estimate in minutes; work logs record minutes.
7. **Rank ordering:** a float `rank` per issue, rebalanced when gaps become too small. Simpler than LexoRank and enough at this scale.
8. **Issue deletion** is allowed for managers/admins only when the issue has no children; it cascades comments, history and attachments (files are removed from disk too).
9. **Mentions:** `@username` in comments notifies the mentioned user if they are a project member.
10. **QA test results:** testers record a result (`passed` / `failed` + notes) on an issue in review.
    A failed result moves the issue back to In Progress; a pass lets the tester move it to Done. Results
    show in the issue's activity history. (Planned for Phase 4.)
11. **Lockout trade-off:** per-account throttling means someone who knows a colleague's email could lock
    them out for 15 minutes. That is acceptable for an internal tool; admins can see attempts in the DB.

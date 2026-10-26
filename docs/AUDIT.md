# Phase 0 Audit — TeamFlow

Branch: `audit-and-baseline` (from `main` @ `0b5ac72`)
Date: 2026-10-25
Owner: Nupur

## 1. Baseline test results

| Command | Folder | Result |
|---|---|---|
| `pytest` | backend | 73 passed, 1 warning (library deprecation in starlette/anyio, not our code) |
| `npm test` | frontend | 2 files, 13 passed |
| `npm run typecheck` | frontend | pass, 0 errors |
| `npm run build` | frontend | pass |

Notes:
- `npm install` reports 12 vulnerabilities (5 moderate, 5 high, 2 critical). Not fixed in this phase; needs a separate reviewed dependency update.
- npm warns that `esbuild` install script is not approved (`allowScripts`). Dev server and build still work.
## 2. Feature matrix (Next-Phase doc vs current code)

Status: Implemented / Partial / Missing / Clarify

| Feature | Phase | Status | Evidence |
|---|---|---|---|
| Subtasks | 1 | Missing | No parent/child field in `backend/app/models/task.py`; no API or UI |
| Task dependencies | 1 | Missing | No dependency table or endpoint |
| Labels | 1 | Missing | No label model/field |
| Watchers | 1 | Missing | No watcher model; notifications go to assignee/related users only |
| Bulk actions | 1 | Missing | Only single-task `PATCH /tasks/{key}` in `routes/tasks.py` |
| Due-date reminders | 1 | Missing | `due_date` exists, but no scheduler/reminder job |
| Sprint & backlog | 2 | Missing | No sprint model, routes or page |
| Story points | 2 | Missing | No field on task |
| Bug & QA workflow | 3 | Partial | Task type `bug` exists (`models/enums.py`), but no severity, repro steps or Open→Fixed→Verified flow |
| GitHub integration | 4 | Deferred | Not started (doc marks it optional/later) |
| Time tracking | 5 | Missing | No estimate/actual time fields |
| Reports & CSV export | 5 | Partial | Dashboard exists (`GET /dashboard`); no CSV export |
| Notifications | 6 | Partial | In-app notifications exist (`routes/dashboard.py`); no reminders/preferences |
| Recurring tasks / automation | 6 | Missing | Not present |

## 3. Already implemented (core app)

- Login/logout, sessions, login lockout after 5 failures (`routes/auth.py`, `services/auth.py`)
- Users & team management, admin role (`routes/users.py`, `models/user.py`)
- Projects with members and archive (`routes/projects.py`)
- Tasks: create/edit/delete, type (task/bug/story), priority, assignee, due date (`routes/tasks.py`)
- Kanban board with status rules (`services/workflow.py`, `pages/BoardPage.tsx`)
- Comments, activity history, notifications, search, dashboard

## 4. Needs clarification (v2 PDF vs current code)

- Board has 4 statuses (To Do, In Progress, **In Review**, Done). v2 PDF asks for 5 (In Testing, **Issue Found**). Change now or later?
- No **Tester** field and no **ETA** on tasks (v2 PDF rules R1–R9). Part of this phase or separate?
- Which Phase 1 feature should be built first?

## 5. Recommended next step

Start Phase 1 with **Subtasks** (smallest safe change, one level only), after review.

## 6. Implementation tracker (next-phase doc, section 10)

| Item | Status | Owner | Notes / evidence |
|---|---|---|---|
| Repository audit | Done | Nupur | This document, sections 1-5 |
| Task enhancements (Phase 1) | Implemented, in review | Nupur | Section 7 below. Tests pass; API checked on the dev server; browser check of the last screens pending |
| Sprint and backlog | Not started | TBD | |
| Bug and QA workflow | Not started | TBD | |
| GitHub integration | Deferred | TBD | |
| Reports and time tracking | Not started | TBD | |
| Notifications and automation | Partial | TBD | Due-date reminders and watcher notifications done in Phase 1; recurring tasks and rules not started |
| Final regression testing | Not started | TBD | |

## 7. Phase 1 report: task enhancements

Branch: `feature/subtasks` (all of Phase 1). Date: 2026-10-26.

### Implemented

| Feature | Main files |
|---|---|
| Subtasks: one level, "x of y done" progress, parent link | `models/task.py` (`parent_id`), `services/tasks.py` (`create_task(parent=)`, `list_subtasks`), `components/tasks/TaskRelations.tsx` (`Subtasks`) |
| Dependencies: depends on / blocks, unfinished-prerequisite warning, self-link and cycle checks | `models/task.py` (`TaskDependency`), `services/task_relations.py`, `TaskRelations.tsx` (`Dependencies`) |
| Labels: per task, lower-case, no duplicates, project suggestions, list filter | `models/task.py` (`TaskLabel`), `services/task_relations.py`, `TaskRelations.tsx` (`Labels`), `pages/TasksPage.tsx` |
| Watchers: watch/unwatch; watchers get status and comment notifications | `models/task.py` (`TaskWatcher`), `services/tasks.py` (`watchers_to_notify`), `services/comments.py`, `TaskRelations.tsx` (`WatchButton`) |
| Bulk actions: assignee, priority, status or label for up to 100 tasks, partial failures listed | `services/task_relations.py` (`bulk_update`), `components/tasks/BulkBar.tsx`, `pages/TasksPage.tsx` |
| Due-date reminders: daily CLI job, once per (task, due date), user opt-out | `services/reminders.py`, `cli.py` (`send-due-reminders`), `models/user.py` (`due_reminders`), `pages/SettingsPage.tsx` |

### Decisions (doc asked to decide and document these)

- **Subtasks** reuse the `tasks` table with `parent_id`, so they keep keys, status, assignee and due
  date. Only one level: a subtask cannot have subtasks, so parent/child loops are impossible.
- **Deleting a parent** is refused (`409 has_subtasks`) while it has subtasks, and the foreign key is
  `ON DELETE RESTRICT` as a backstop. Nothing is orphaned or deleted silently.
- **Dependencies** only warn. Status changes are never blocked, as the doc requires unless the team
  approves blocking. Same project only.
- **Bulk actions** apply one change per request. Each task is checked and saved on its own, so one
  failure doesn't undo the others and the response lists every failure.
- **Reminders** run from a CLI command scheduled once a day, not inside the API, so several API workers
  can't send duplicates. "Due soon" means today or tomorrow (`--days-ahead` to change). Dates use the
  server's date.

### Already existed

Task `due_date`, in-app notifications, activity history, role permissions and `get_task` access
checks. Phase 1 reuses all of these instead of adding parallel versions.

### Database

- `20261026_44046dd740bc`: `tasks.parent_id` (FK RESTRICT, indexed)
- `20261026_746ca5557fee`: `task_dependencies`, `task_labels`, `task_watchers`, `task_reminders`,
  `users.due_reminders` (default true), and the `task_due` notification type

Tested on a copy of the dev database: `alembic upgrade head`, `downgrade -1`, `upgrade head`; existing
users and tasks kept, `alembic check` reports no drift. The test suite builds its schema from these
migrations.

### API

New: `GET/POST /tasks/{key}/subtasks`, `GET/POST /tasks/{key}/dependencies`,
`DELETE /tasks/{key}/dependencies/{other}`, `POST /tasks/{key}/labels`,
`DELETE /tasks/{key}/labels/{name}`, `POST/DELETE /tasks/{key}/watch`, `POST /tasks/bulk`,
`GET /projects/{key}/labels`. Changed: `GET /tasks?label=`, `PATCH /auth/me` takes `due_reminders`,
task responses include `parent_key` and `labels`, task detail includes `watchers` and `watching`.
Permissions: everything goes through `get_task`/`get_project` (non-members get 404). Changing
dependencies and labels needs the same right as editing the task; creating subtasks needs the same
right as creating a task. Details in [API.md](API.md).

### Frontend

Task detail: parent link, Subtasks section, Dependencies section, Labels row, Watch button. Task
list: checkboxes, bulk action bar with confirmation and a failure list, label filter, labels and
parent shown under the title. Settings: due-date reminders switch.

### Tests

| Command | Folder | Result |
|---|---|---|
| `pytest` | backend | 106 passed (73 before + 8 subtasks + 25 dependencies/labels/watchers/bulk/reminders) |
| `ruff check app tests` | backend | pass |
| `npm run typecheck` | frontend | pass |
| `npm test` | frontend | 13 passed |
| `npm run build` | frontend | pass |

### Manual verification

On the dev server with the sample data (`seed-dev`), 2026-10-27:

- **In the browser (Nupur):** subtasks. Added two subtasks to TF-3 and saw "0 of 2 done"; the
  subtask page shows "Subtask of TF-3" and has no Subtasks section; Rahul moved a subtask to In
  Review, Priya (tester) moved it to Done, and the parent showed "1 of 2 done" with the progress bar.
- **Through the API as Rahul and Priya, the same calls the UI buttons make:** dependency added and
  listed on both tasks with the unfinished warning count; self-link, other-project link and editing
  someone else's task rejected (422/422/403). Label normalized and not duplicated, label filter works.
  Watching TF-3 gave Priya a notification for Rahul's comment. Bulk priority on TF-3, TF-4, TF-99
  updated TF-3 and reported the other two with their reasons. Reminder setting toggles.
  `send-due-reminders` ran twice: 2 tasks the first time, 0 the second.
- **Still to check by eye in the browser:** dependencies, labels and watch button on the task page,
  the bulk bar on the task list, and the reminder switch in Settings.

### Known limitations

- Moving an existing task under a parent (or out of one) is not supported. Subtasks are created from
  the parent.
- Bulk status changes follow the normal workflow, so To Do cannot jump straight to Done.
- Reminders use the server's date, not each user's time zone.
- The frontend has no automated tests for the new screens (existing frontend tests cover auth only).

### Next recommendation

Review and merge Phase 1. Then Phase 2 (sprints and backlog), starting with the sprint model and
backlog view.

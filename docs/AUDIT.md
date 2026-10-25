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

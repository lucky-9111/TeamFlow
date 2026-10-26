# Local development

Requirements: **Python 3.12 or 3.13** (not 3.14 alpha), Node 22+, Git.

## Backend

### First-time setup

Windows (PowerShell):

```powershell
cd backend
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
alembic upgrade head
python -m app.cli create-admin --email you@company.com --username you --full-name "Your Name"
```

Linux / macOS:

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
python -m app.cli create-admin --email you@company.com --username you --full-name "Your Name"
```

`create-admin` prompts for the password (or reads `TEAMFLOW_ADMIN_PASSWORD`). It refuses to run once
an admin exists. Later users are created by an admin in the app.

The development database is `backend/data/teamflow.db` (git-ignored).

### Run

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000/api/v1
- Interactive docs (development only): http://localhost:8000/api/docs

### Tests and lint

```bash
cd backend
pytest            # uses a throwaway SQLite DB in the OS temp dir; never touches data/
ruff check .
ruff format --check .
```

### Changing the database schema

1. Edit models in `app/models/` (and import new modules in `app/models/__init__.py`).
2. `alembic revision --autogenerate -m "describe change"`
3. Review the generated file in `alembic/versions/`. Autogenerate is a draft, not a guarantee.
4. `alembic upgrade head`, then run `pytest` (tests build the schema from migrations).

### Maintenance commands

```bash
python -m app.cli cleanup                 # prune expired sessions and old login attempts
python -m app.cli send-due-reminders      # notify about open tasks due today or tomorrow
python -m app.cli send-due-reminders --days-ahead 3
```

**Due-date reminders** are not started by the API (several API workers would otherwise send
duplicates). Schedule the command once a day: cron on Linux (`0 8 * * * cd /srv/teamflow/backend &&
.venv/bin/python -m app.cli send-due-reminders`) or Windows Task Scheduler. Re-running it is safe:
each (task, due date) is reminded once, recorded in `task_reminders`. Changing a due date makes the
task eligible again. Users can turn reminders off in Settings. If a run fails, the next run picks up
anything still due; the command prints how many tasks it reminded.

## Frontend

```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to http://127.0.0.1:8000
npm test           # Vitest
npm run typecheck
npm run build      # output in frontend/dist
```

Layout of `frontend/src`:

- `services/api.ts`: the only place that calls `fetch` (cookies, CSRF header, error mapping, 401 handling)
- `hooks/queries.ts`: TanStack Query hooks per resource, plus `invalidateTaskViews` after task changes
- `features/auth`: current user, login/logout, route guard (including the forced password change)
- `layouts/`: app shell (sidebar, top bar, search, notifications)
- `pages/`: one file per screen
- `components/ui`: buttons, dialogs, toasts, empty/error states; `components/tasks`: task badges, rows, create dialog
- `types/api.ts`: TypeScript copies of the backend schemas. Update them when you change `backend/app/schemas`.

## Sample data

```powershell
cd backend
python -m app.cli seed-dev
```

Creates projects `TF` and `MOB`, 11 tasks in different states, and four users
(`rahul@`, `priya@`, `amit@`, `sneha@example.com`, password `teamflow-demo-123`). It needs an
existing admin, refuses in production, and exits without changes if the projects already exist.

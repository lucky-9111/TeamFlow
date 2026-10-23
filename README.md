# TeamFlow

Internal project-management tool (Jira-inspired) for a small team of 2–10 people: projects, tasks,
a Kanban board, comments, activity history, notifications and a team overview.

| Part     | Stack                                                                   | Folder      |
|----------|-------------------------------------------------------------------------|-------------|
| Backend  | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, SQLite, Pydantic           | `backend/`  |
| Frontend | React 18, Vite, TypeScript, React Router, TanStack Query, Tailwind CSS, dnd-kit | `frontend/` |

More docs: [Architecture](docs/ARCHITECTURE.md) · [API reference](docs/API.md) · [Development notes](docs/DEVELOPMENT.md)

---

## Run it locally (Windows 11)

You need **Python 3.13** (3.12 also works; not the 3.14 alpha), **Node.js 22 or newer**, and Git.
Check with `py -3.13 --version` and `node -v`.

You will run **two terminals**: one for the backend, one for the frontend.

### 1. Backend (first time)

Open PowerShell in the project folder:

```powershell
cd backend
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
alembic upgrade head
python -m app.cli create-admin --email you@company.com --username you --full-name "Your Name"
```

- `create-admin` asks for a password (at least 10 characters). It only works once; add other people
  from the **Team** page in the app.
- Optional sample data (2 projects, 11 tasks, 4 users with the password `teamflow-demo-123`):

  ```powershell
  python -m app.cli seed-dev
  ```

  It refuses to run in production and does nothing if the sample projects already exist.

If PowerShell blocks `Activate.ps1`, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### 2. Backend (every time)

```powershell
cd backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

- API: http://127.0.0.1:8000/api/v1
- Interactive API docs: http://127.0.0.1:8000/api/docs

### 3. Frontend (first time, in a second terminal)

```powershell
cd frontend
npm install
```

### 4. Frontend (every time)

```powershell
cd frontend
npm run dev
```

Open the URL Vite prints, normally **http://localhost:5173**, and sign in.

The frontend calls `/api/...` on its own address and Vite forwards those requests to the backend
on port 8000, so you don't need any CORS setup. Opening http://127.0.0.1:8000 directly shows only
the API, not the app.

---

## Tests and checks

```powershell
# backend
cd backend
pytest              # uses a throwaway database in your temp folder; never touches data/
ruff check .

# frontend
cd frontend
npm test            # Vitest + Testing Library
npm run typecheck
npm run build       # production build into frontend/dist
```

## Configuration

- Backend settings live in `backend/.env` (copy of `backend/.env.example`). All names start with
  `TEAMFLOW_`. The database is `backend/data/teamflow.db` by default.
- Frontend settings (optional) live in `frontend/.env` (copy of `frontend/.env.example`).
  `VITE_BACKEND_URL` changes where Vite forwards API calls.
- Never commit `.env` files; they are git-ignored.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| The app says "Cannot reach the TeamFlow server" | The backend isn't running. Start it (step 2) and reload. |
| `alembic` or `uvicorn` is "not recognized" | Activate the virtual environment first: `.venv\Scripts\Activate.ps1`. |
| `pip install` fails building `pydantic-core` | You're on Python 3.14 alpha. Create the venv with `py -3.13`. |
| Login says "Too many failed login attempts" | Wait 15 minutes, or lower `TEAMFLOW_LOGIN_LOCKOUT_MINUTES` in `.env` for development. |
| Port 5173 or 8000 is already in use | Stop the other process, or run `npm run dev -- --port 5174` / `uvicorn ... --port 8001` (then set `VITE_BACKEND_URL` to match). |
| `ZoneInfoNotFoundError` on Windows | Run `pip install -r requirements.txt` again; it installs `tzdata`. |
| "Missing or invalid CSRF token" | Sign out and in again. The app also refreshes the token automatically once. |
| A board move is refused | The workflow only allows certain moves, and only for certain people. The message says which. See "How tasks move" below. |

## How tasks move

```
To Do  →  In Progress  →  In Review  →  Done
          ↑    ↓                ↓          ↓
          To Do            In Progress   In Progress (reopen)
```

- The **assignee** (or the reporter, while nobody is assigned) moves the task through To Do,
  In Progress and In Review.
- A project **tester** decides after review: Done, or back to In Progress. Testers can also reopen Done tasks.
- Project **managers** and workspace **admins** can make any valid move.
- Moves that skip a step (To Do → Done, for example) are rejected by the backend, whatever the screen shows.

## Roles

| Who | Can |
|-----|-----|
| Workspace admin | Everything: add/deactivate people, create/archive projects, all project actions |
| Project manager | Edit the project, manage its members, edit/assign/delete any task, any status move, moderate comments |
| Developer / designer | See the project, create tasks (unless the project turns that off), edit tasks they report or are assigned, comment |
| Tester | Same as developer, plus review: In Review → Done / In Progress, reopen Done |

All checks happen in the backend (`backend/app/core/permissions.py` and `app/services/`). The
frontend only hides buttons the API would refuse anyway.

## Before deploying to a real server

This runs well locally. It is **not production-ready by itself**. Before exposing it:

- Serve it over HTTPS and set `TEAMFLOW_ENV=production` and `TEAMFLOW_COOKIE_SECURE=true`.
- Build the frontend (`npm run build`) and serve `frontend/dist` and the API from the **same origin**
  (for example Nginx serving the files and proxying `/api` to Uvicorn). Cookies and CSRF rely on this.
- Run a single Uvicorn process (SQLite allows one writer at a time), keep `backend/data/` outside any
  public folder, and back up `teamflow.db` regularly (with the server stopped, or using SQLite's backup command).
- Schedule `python -m app.cli cleanup` daily to prune old sessions and login attempts.
- No email is sent: an admin gives new members their temporary password directly.

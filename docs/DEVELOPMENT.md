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
python -m app.cli cleanup      # prune expired sessions and old login attempts
```

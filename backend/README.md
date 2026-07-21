# AegisTwin Backend Foundation

Python 3.11+ is required. The service refuses to start unless simulation-only mode is enabled. Run commands from the `backend` directory.

## Windows CMD

```bat
cd backend
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
copy .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another activated CMD session:

```bat
cd backend
.venv\Scripts\activate.bat
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m ruff format .
python -m mypy app tests
```

## Windows PowerShell

```powershell
Set-Location backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another activated PowerShell session:

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m ruff format .
python -m mypy app tests
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process RemoteSigned` for the current process only, or invoke `.venv\Scripts\python.exe -m ...` directly.

## Migrations

Apply committed migrations with `python -m alembic upgrade head`. Generate a future reviewed migration with `python -m alembic revision --autogenerate -m "description"`. Do not perform destructive downgrades as part of normal setup.

## Configuration

Settings are read from environment variables and an optional local `.env`. `CORS_ORIGINS` accepts a comma-separated string or JSON array. Never commit `.env`. `SIMULATION_ONLY=false` is prohibited and prevents startup.


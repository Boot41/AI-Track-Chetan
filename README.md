# App Scaffold

Full-stack scaffold with FastAPI + React + PostgreSQL. All tooling, quality gates, Docker, and CI/CD pre-configured — zero business logic, ready to build on.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16 |
| Frontend | React 18, TypeScript, Vite 5, Material-UI v6 |
| Package Managers | uv (Python), npm (Node) |
| Quality | Ruff, MyPy (strict), import-linter, ESLint, TypeScript strict |
| Containers | Docker, Docker Compose |
| CI | GitHub Actions |

## Project Structure

```
.
├── .github/workflows/ci.yml    # CI pipeline
├── docker-compose.yml           # PostgreSQL + API + Client
├── Dockerfile                   # Multi-stage production build
├── server/                      # FastAPI backend
│   ├── app/
│   │   ├── api/routes/          # HTTP endpoints
│   │   ├── auth/                # JWT auth + bcrypt
│   │   ├── core/                # Config + logging
│   │   ├── db/                  # SQLAlchemy models + session
│   │   ├── middleware/          # Error handler + request logging
│   │   ├── services/            # Business logic layer
│   │   └── main.py              # App factory
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # Unit + integration tests
│   └── pyproject.toml           # Dependencies + tool config
└── client/                      # React frontend
    ├── src/
    │   ├── App.tsx              # Router + pages
    │   ├── main.tsx             # Entry point + providers
    │   └── lib/api.ts           # Axios instance
    ├── package.json             # Dependencies + scripts
    └── Dockerfile               # Node build → Nginx
```

## Module Boundaries

- `app.api` depends on `app.services`, `app.auth`, `app.core` only
- `app.services` depends on `app.db`, `app.core` only (must NOT import from `app.api`)
- `app.db` depends on `app.core` only (must NOT import from `app.services` or `app.api`)
- Enforced by `import-linter` in CI

## Quick Start

```bash
# Start PostgreSQL
docker-compose up -d db

# Backend
cd server
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8010

# Frontend (separate terminal)
cd client
npm install
npm run dev
```

App runs at http://localhost:5173 with API proxied to :8010.

## Quality Gates

Backend (from `server/`):
```bash
uv run ruff format --check .    # Formatting
uv run ruff check .             # Linting
uv run mypy .                   # Type checking (strict)
uv run lint-imports             # Module boundaries
uv run pytest tests/unit -q     # Unit tests
uv run pytest tests/integration -q  # Integration tests
```

Frontend (from `client/`):
```bash
npm run lint    # ESLint
npm run build   # TypeScript + Vite build
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| POST | `/auth/login` | No | Returns JWT token |
| * | `/api/v1/*` | Bearer | Protected routes (add yours here) |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | `development` | development / test / production |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5433/app_scaffold` | Database connection |
| `SECRET_KEY` | `app-scaffold-dev-secret` | JWT signing secret |

## Docker

```bash
# Development (3 services)
docker-compose up

# Production (single image)
docker build -t app-scaffold .
```

## Coding Style

- Python: 4-space indent, type hints, `snake_case` functions, `PascalCase` classes
- TypeScript: strict mode, `PascalCase` components, `camelCase` utilities
- Backend layering: Routes → Services → DB (enforced)
- Conventional Commits: `feat:`, `fix:`, `refactor:`

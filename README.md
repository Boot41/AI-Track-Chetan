# OTT Content Investment Decision Platform

AI-powered application for OTT streaming platform executives and analysts to evaluate whether to greenlight original series or acquire movie catalogs. The platform combines structured PostgreSQL data with unstructured local documents to produce a recommendation, a structured scorecard, and supporting evidence.

## Product Goal

The application is intended to help decision-makers answer questions such as:

- Should we greenlight this original series?
- Should we acquire this movie catalog?
- Which content opportunity is the better investment?
- What are the biggest narrative, commercial, and contractual risks?
- How strong is the projected ROI and catalog fit?

Each evaluation should produce:

- a natural-language explanation
- a structured JSON scorecard
- evidence from retrieved data and documents
- minimal user-facing uncertainty metadata

## Architecture

The application is split into three services that run on separate servers:

1. `client/`
   React frontend for login, chat, scorecard rendering, and evidence display.
2. `server/`
   FastAPI backend for JWT authentication, user/session management, protected APIs, and inter-service calls to the agent.
3. `agent/`
   Standalone Google ADK-based agent service for retrieval, reasoning, scoring, and recommendation generation.

Design principle:

- keep the frontend thin
- keep the backend thin
- keep retrieval, reasoning, scoring, and recommendation logic in the standalone agent service

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16 |
| Frontend | React 18, TypeScript, Vite 5, current repo uses Material-UI |
| Agent | Google ADK |
| Package Managers | uv (Python), npm (Node) |
| Quality | Ruff, MyPy (strict), import-linter, ESLint, TypeScript strict, Playwright, agent evals |
| Containers | Docker, Docker Compose |
| CI | GitHub Actions |

## Responsibilities By Service

### Frontend

- JWT login page
- chat interface
- structured scorecard rendering
- evidence and source display

The frontend should not own business logic, retrieval logic, or scoring logic.

### Backend

- JWT authentication and user validation
- chat APIs
- session storage per user
- authorization before invoking the agent
- inter-service calls to the standalone agent service
- forwarding trusted identity and session context

The backend should not own prompt-heavy reasoning, narrative analysis, ROI logic, or contract analysis.

### Agent

- natural-language query understanding
- retrieval from PostgreSQL and indexed documents
- narrative analysis of scripts and show bibles
- contract and risk analysis
- ROI and viewership prediction
- catalog fit scoring
- recommendation synthesis
- final JSON scorecard generation

Most domain intelligence belongs here.

## Auth And Trust Boundary

Authentication is JWT-based and enforced by the backend.

Rules:

- users must authenticate before accessing chat
- backend validates JWT tokens
- backend extracts trusted identity such as `user_id` and `session_id`
- backend makes inter-service calls to the standalone agent service
- backend forwards trusted identity and session context to the agent
- the agent service must not accept raw end-user JWTs for privileged operations
- the agent service must not perform end-user authentication
- the agent trusts backend-forwarded identity and context only

If service-to-service authentication is added later, keep it separate from end-user authentication.

## Data Sources

### PostgreSQL

The structured data layer is expected to include:

- historical viewership metrics
- completion rates
- episode drop-off rates
- subscriber demographic data
- production budgets
- licensing costs
- regional localization costs
- competitor catalog metadata

### Local Documents

The document repository is expected to include:

- pilot scripts
- show bibles
- director pitch decks
- focus group sentiment reports
- licensing contracts

Documents are assumed to already exist in local/project context. Do not design around manual upload as the primary workflow unless explicitly required.

## Document Processing And Retrieval

During ingestion, documents should be:

- parsed with PyMuPDF where applicable
- split into semantic sections such as scenes, clauses, slides, and report sections
- stored in PostgreSQL for indexing and retrieval

Core document tables should include:

- `documents`
- `document_sections`
- `document_facts`
- `document_risks`

For MVP, `document_facts` should be populated primarily with contract-derived atomic facts tied to source sections.

Retrieval strategy:

- `pgvector` for semantic retrieval
- PostgreSQL full-text search for lexical retrieval
- metadata filters for narrowing by source and business context

Retrieval quality should be improved through chunking, metadata, and ranking before increasing prompt complexity.

## Agent Design

The target agent architecture includes a main orchestrator that decides which subagents and tools to invoke.

Suggested subagents:

- Document Retrieval Agent
- Narrative Analysis Agent
- ROI Prediction Agent
- Risk & Contract Analysis Agent
- Catalog Fit Agent

Suggested tools:

- vector search tool
- SQL query tool
- narrative feature extractor
- contract clause extractor
- deterministic scoring helpers

## Output Contract

The public response contract should be stable and easy for the frontend to render without heuristic parsing.

Required top-level fields:

- `answer`
- `scorecard`
- `evidence`
- `meta`

The `meta` field is intentionally minimal and user-facing:

- `warnings`
- `confidence`
- `review_required`

Expected scorecard fields include:

- projected completion rate
- estimated ROI
- catalog fit score
- risk flags
- final recommendation

## Repository Layout

```text
.
├── .github/workflows/         # CI configuration
├── AGENTS.md                  # agent/contributor operating guidance
├── docs/                      # planning/spec artifacts
├── agent/                     # standalone ADK agent service area
│   └── my_agent/
├── client/                    # React frontend
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── server/                    # FastAPI backend
│   ├── alembic/
│   ├── app/
│   │   ├── agent/            # current scaffold agent wiring inside backend
│   │   ├── api/routes/
│   │   ├── auth/
│   │   ├── core/
│   │   ├── db/
│   │   ├── middleware/
│   │   ├── services/
│   │   └── main.py
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
└── docker-compose.yml
```

## Current Repo Status

The repository currently contains scaffold and early implementation pieces for:

- FastAPI authentication and API routes
- React frontend shell
- backend-side agent wiring under `server/app/agent/`
- a separate `agent/my_agent/` ADK entrypoint

The target product direction is still to keep the long-term domain intelligence in the standalone `agent/` service.

## Planning Documents

Supporting documents currently present in the repo:

- `docs/SPEC.md`
- `docs/Solutions.md`
- `AGENTS.md`

Use them together when working on architecture-heavy changes.

## Local Development

### Backend

```bash
cd server
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8010
```

### Frontend

```bash
cd client
npm install
npm run dev
```

### Agent

The current standalone agent entrypoint is `agent/my_agent/agent.py`.

Use the ADK command that matches your local setup once the agent service is wired for standalone execution in this repo.

## Testing Strategy

Testing must cover backend, agent service, and frontend.

### Unit Tests

Use `pytest` for:

- parser helpers
- sectioners
- retrieval helpers
- scorers
- formatters
- schema validation
- auth helpers

### Integration Tests

Use `pytest` for:

- document ingestion pipeline
- retrieval and ranking
- backend and agent service communication
- persistence of chat sessions and evaluation results
- backend auth and protected API flows

### End-To-End Tests

Use Playwright for:

- login flow
- protected chat access
- chat interaction
- scorecard rendering
- evidence panel rendering

### Agent Evaluation Tests

Use pytest-based eval suites for:

- retrieval grounding
- risk detection accuracy
- recommendation stability
- schema validity
- follow-up conversation handling

## Quality Gates

### Backend

From `server/`:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run lint-imports
uv run pytest tests/unit -q
uv run pytest tests/integration -q
```

### Frontend

From `client/`:

```bash
npm run lint
npm run build
```

### Planned Additions

- Playwright command from `client/` once the E2E suite is added
- dedicated agent eval runner under `agent/`

## Current API Surface

Current backend endpoints include:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| POST | `/auth/login` | No | Returns JWT token |
| POST | `/api/v1/agent/run` | Bearer | Runs the current backend-wired agent path |

Current code still includes backend-local agent wiring. As the architecture matures, the backend should call the standalone `agent/` service over an internal service boundary.

The standalone agent service should not directly trust browser clients for privileged operations; the backend is the trust boundary for end-user authentication.

## Environment Variables

### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | `development` | development / test / production |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5433/app_scaffold` | Database connection |
| `SECRET_KEY` | `app-scaffold-dev-secret` | JWT signing secret |

### Agent

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | *(empty)* | Google AI Studio API key for ADK |
| `GOOGLE_GENAI_USE_VERTEXAI` | `false` | Set `true` to use Vertex AI instead |

## Engineering Guidance

- Keep business intelligence in `agent/`
- Keep backend routes thin
- Keep frontend focused on interaction and presentation
- Preserve traceability from evidence to recommendation
- Prefer typed schemas for structured outputs

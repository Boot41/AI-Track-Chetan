# Agent Map

This file is a map, not a full manual. Use it to quickly find the source of truth for architecture, agent behavior, implementation rules, and delivery expectations for this OTT decision-support application.

## Product North Star

This application is an internal AI decision-support system for OTT streaming executives and analysts.

It helps evaluate whether the platform should:

- greenlight a new original series
- acquire an existing movie or content catalog
- compare multiple content opportunities before allocating budget

The system combines structured PostgreSQL metrics with unstructured local documents and agent-driven reasoning to produce:

- a natural-language recommendation
- a structured JSON scorecard
- evidence-backed risk and opportunity analysis

This is an internal strategic decision-support product, not a consumer OTT experience.

## Start Here

Primary source of truth files:

- Product and architecture spec: `docs/SPEC.md`
- Agent architecture and operating model: `AGENTS.md`
- Implementation plan and testing strategy: `docs/Solutions.md`

When making changes, read all three before coding in unfamiliar areas.

## Architecture Map

### System Shape

The application is split into three separately deployed services:

- `client/` — React frontend
- `server/` — FastAPI backend
- `agent/` — standalone Google ADK-based agent service

### Responsibilities by Service

#### Frontend
Owns:
- login flow
- chat interface
- scorecard rendering
- evidence display

Must not own:
- business logic
- scoring logic
- retrieval logic
- document reasoning
- auth validation beyond client UX state

#### Backend
Owns:
- JWT auth
- user/session persistence
- protected APIs
- request validation
- routing trusted requests to the agent service

Must not own:
- prompt-heavy reasoning
- narrative analysis
- ROI logic
- contract analysis
- catalog fit decisions

#### Agent Service
Owns:
- query understanding
- retrieval planning
- document and SQL retrieval
- narrative analysis
- contract/risk analysis
- ROI prediction
- catalog fit scoring
- recommendation synthesis
- scorecard generation

## Code Map

### Frontend
- `client/src/`

### Backend
- `server/app/api/routes/` — HTTP routes
- `server/app/auth/` — JWT/password/auth dependencies
- `server/app/services/` — thin backend service logic
- `server/app/db/` — DB models, sessions, persistence
- `server/app/schemas/` — typed request/response models

### Agent
- `agent/app/agents/` — orchestrator and subagents
- `agent/app/tools/` — explicit agent tools
- `agent/app/retrieval/` — hybrid retrieval logic
- `agent/app/ingestion/` — document ingestion and indexing
- `agent/app/scorers/` — deterministic scoring helpers
- `agent/app/formatters/` — response and scorecard formatters
- `agent/app/schemas/` — typed agent contracts
- `agent/app/prompts/` — modular prompt assets
- `agent/app/services/` — internal orchestration helpers

## Non-Negotiable Engineering Rules

- Keep frontend thin.
- Keep backend thin.
- Put domain intelligence in the agent layer.
- Use descriptive file, module, component, and test names based on responsibility, not roadmap phase labels.
- Do not move scoring, retrieval, or reasoning into API route handlers.
- Do not make the frontend responsible for business decisions.
- Prefer explicit tools and subagents over one large opaque prompt.
- Preserve source traceability from retrieved evidence to final recommendation.
- Preserve stable typed response contracts.
- Prefer deterministic post-processing for scorecards whenever possible.
- Do not fabricate evidence, clauses, or metrics.
- If retrieval confidence is low, return uncertainty explicitly.

### Naming Rule

- Roadmap phases such as `Phase 0`, `Phase 1`, and later phases are planning labels only.
- Do not create long-lived modules or test files named like `phase0.py`, `phase1.py`, `test_phase0_schemas.py`, `phase_2.ts`, or similar.
- Do not refer to implementation code, runtime strings, comments, docstrings, test names, agent names, or user-facing/internal wording by roadmap phase labels such as `Phase 3` or `Phase 4`.
- Prefer names such as `contracts.py`, `chat_api.py`, `public-contract.ts`, `agent_client.py`, or other responsibility-based names.
- Prefer test names such as `test_contract_schemas.py`, `test_chat_api.py`, or `contract-stub.spec.ts`.
- Fixture directories or migration identifiers may retain phase labels when they are explicitly tied to roadmap artifacts or historical ordering.

## Agent Standard

The agent service uses Google ADK and should preserve explicit agent boundaries.

### Required shape

- one main orchestrator
- focused subagents
- explicit tools
- scorer modules
- formatter modules

### Required subagents

- `Document Retrieval Agent`
- `Narrative Analysis Agent`
- `ROI Prediction Agent`
- `Risk & Contract Analysis Agent`
- `Catalog Fit Agent`

### Required supporting modules

#### Tools
- vector search tool
- SQL query tool
- narrative feature extractor
- contract clause extractor
- retrieval/ranking helpers

#### Scorers
- completion rate scorer
- ROI scorer
- catalog fit scorer
- risk severity scorer
- recommendation engine

#### Formatters
- scorecard formatter
- chat response formatter
- evidence formatter

## Data Map

### Structured data
PostgreSQL is the source of truth for:
- historical viewership metrics
- completion/drop-off metrics
- subscriber demographics
- production budgets
- licensing costs
- localization costs
- competitor catalog metadata
- document indexing tables
- auth/session persistence
- evaluation persistence

### Local documents
Documents are preexisting and live in local storage/project context.

Expected types:
- pilot scripts
- show bibles
- pitch decks
- focus group reports
- licensing contracts

Do not assume document upload flows.

## Document Handling Rules

Documents must be ingested before runtime retrieval.

Required pipeline:
- parse document files with PyMuPDF where applicable
- split into semantic sections, not naive full-document blobs
- preserve source metadata
- index sections into PostgreSQL

Preferred sectioning:
- scripts by scene or beat
- contracts by clause or provision
- decks by slide
- reports by section/subsection

Core tables:
- `documents`
- `document_sections`
- `document_facts`
- `document_risks`

## Retrieval Rules

Use hybrid retrieval:
- `pgvector` for semantic similarity
- PostgreSQL full-text search for exact/lexical recall
- metadata filtering for narrowing

Improve retrieval quality before increasing prompt complexity.

Prefer:
- better chunking
- better metadata
- better ranking
over:
- larger prompts
- whole-document stuffing

## Auth and Trust Boundary

Authentication is JWT-based.

Rules:
- users must authenticate before accessing chat
- backend validates JWT
- backend makes an inter-service call to the standalone agent service
- backend passes trusted `user_id` and session context to the agent
- the agent must not trust client-supplied user IDs
- the agent must not perform end-user JWT authentication
- the agent must not accept client-originated requests for privileged operations
- the agent trusts backend-forwarded identity and context only

If service-to-service auth is later needed, keep it separate from user auth.

## Testing and Quality Gates

Testing is required across backend, agent, and frontend.

### Required test layers

#### Unit tests
Use `pytest` for:
- parser helpers
- sectioners
- retrieval helpers
- scorers
- formatters
- auth helpers
- schemas

#### Integration tests
Use `pytest` for:
- ingestion pipeline
- retrieval pipeline
- backend auth flow
- backend-agent communication
- persistence of chat/evaluation results

#### End-to-end tests
Use `Playwright` for:
- login flow
- protected chat access
- chat interaction
- scorecard rendering
- evidence rendering

#### Agent evals
Use eval suites for:
- retrieval quality
- evidence grounding
- recommendation consistency
- schema stability
- follow-up question behavior
- comparison reasoning

## Delivery Flow

Before coding:
1. read `docs/SPEC.md`
2. read `docs/Solutions.md`
3. check touched service boundaries
4. define the smallest mergeable feature slice

Implementation order should follow the plan in `docs/Solutions.md`.

Preferred flow:
1. write or update failing tests
2. implement minimal change
3. refactor with tests green
4. keep contracts stable
5. commit before moving to the next feature slice

## Definition of Done

For any completed change:
- tests are added or updated
- changed behavior is covered
- typed contracts remain valid
- architecture boundaries are respected
- retrieval/scoring/output traceability is preserved
- JSON output remains stable for frontend rendering
- git changes are in a mergeable state
- for every PR raised, the PR description includes a detailed summary of the change
- before every push, ensure `.github/workflows/ci.yml` passes

## Change Heuristics for Future Agents

When making a change, first ask:

- does this belong in frontend, backend, or agent?
- is this reasoning logic that should live in the agent?
- is this route becoming too heavy?
- is this output stable and typed?
- can this be implemented as a tool, scorer, or formatter instead of prompt sprawl?
- does this preserve provenance and evidence traceability?
- does this need unit, integration, Playwright, or eval coverage?

Default behavior:
- keep UI simple
- keep backend thin
- keep intelligence in the agent layer

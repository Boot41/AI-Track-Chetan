# Implementation Strategy

The system is implemented as a thin frontend, thin backend, and an intelligence-heavy agent service.

Principles:

- UI handles input and display only.
- Backend handles authentication and request routing.
- Agent service owns reasoning, retrieval, and decision synthesis.

---

# Technology Stack

Frontend
- React
- Vite
- Playwright for E2E testing

Backend
- FastAPI
- PostgreSQL
- JWT authentication
- Pydantic schemas

Agent Service
- Python
- Google ADK for orchestration
- pgvector for embeddings
- PyMuPDF for document parsing

Testing
- pytest
- integration tests
- Playwright E2E tests
- agent evaluation suites

---

## Repo Structure

Current repo top level:

```text
client/
server/
agent/
docs/
```

Current test locations:

```text
server/tests/
```

Target agent service layout:

```text
agent/
  app/
    agents/
    tools/
    retrieval/
    ingestion/
    scorers/
    formatters/
    prompts/
    schemas/
```

---

# Agent Architecture

The agent service uses **Google ADK**.

## Main Orchestrator

Responsibilities:

- classify user request
- determine required tools
- coordinate subagents
- synthesize final response

---

## Subagents

### Document Retrieval Agent

Responsible for retrieving relevant document sections.

Uses:

- vector search
- full-text search
- metadata filters

---

### Narrative Analysis Agent

Extracts narrative signals from scripts and show bibles.

Outputs:

- genre
- themes
- tone
- pacing
- character arcs
- franchise potential

---

### ROI Prediction Agent

Estimates performance metrics.

Inputs:

- narrative features
- budgets
- historical metrics

Outputs:

- completion estimate
- retention lift
- ROI
- cost-per-view

---

### Risk & Contract Analysis Agent

Analyzes contracts for legal risks.

Outputs:

- risk flags
- severity
- rationale

---

### Catalog Fit Agent

Scores strategic alignment.

Outputs:

- fit score
- target demographics
- strategy alignment

---

# Agent Runtime Flow

1. Backend validates JWT.
2. Backend extracts trusted identity and session context.
3. Backend makes an inter-service call to the standalone agent service.
4. Orchestrator classifies request.
5. Retrieval agent fetches relevant evidence.
6. Specialist subagents analyze evidence.
7. Scorers compute metrics.
8. Formatters generate output.
9. Agent returns response.

---

# Document Ingestion Pipeline

Documents are processed during ingestion.

Steps:

1. Parse document using PyMuPDF.
2. Detect semantic sections.
3. Extract metadata.
4. Generate embeddings.
5. Store sections in PostgreSQL.

Local storage structure:

```text
data/raw/
data/parsed/
data/cache/
```

---

# Database Design

Core document tables:

- documents
- document_sections
- document_facts
- document_risks

Additional application tables:

- users
- chat_sessions
- chat_messages
- evaluation_results

---

# Retrieval Pipeline

Hybrid retrieval:

1. metadata filtering
2. keyword search
3. vector similarity
4. reranking

Each evidence result must include:

- document id
- section id
- snippet
- page reference

---

# Scorers

Scorers compute stable decision metrics.

Modules:

- completion_rate_scorer
- roi_scorer
- catalog_fit_scorer
- risk_severity_scorer
- recommendation_engine

---

# Formatters

Formatters normalize outputs.

Modules:

- scorecard_formatter
- response_formatter
- evidence_formatter

---

# Authentication Flow

1. User logs in.
2. Backend validates JWT.
3. Backend extracts trusted `user_id` and session context.
4. Backend makes an inter-service call to the standalone agent service.
5. Agent processes request using backend-forwarded context.

Agent must never perform user authentication or accept client-originated privileged requests.

---

# Branch Strategy

Example feature branches:

```text
feat/document-parser
feat/document-sectioner
feat/pgvector-indexing
feat/hybrid-retriever
feat/agent-orchestrator
feat/narrative-agent
feat/roi-agent
feat/risk-agent
feat/catalog-fit-agent
feat/scoring-engine
feat/frontend-chat
```

---

# Testing Strategy

## Unit Tests

Use `pytest` for:

- parser helpers
- sectioners
- retrieval helpers
- scorers
- formatters
- auth helpers
- schema validation

---

## Integration Tests

Use `pytest` for:

- ingestion pipeline
- retrieval pipeline
- backend and agent communication
- session persistence
- evaluation persistence

---

## End-to-End Tests

Use `Playwright`.

Test:

- login flow
- protected chat access
- chat interaction
- scorecard rendering
- evidence display

---

## Agent Evaluation Tests

Use pytest-based eval suites to verify:

- recommendation stability
- retrieval grounding
- risk detection accuracy
- schema validity
- comparison reasoning
- follow-up conversation handling

Example eval case:

```python
{
  "query": "Should we acquire this catalog?",
  "expected_recommendation": "conditional_acquire",
  "required_risk": "territory_restriction"
}
```

---

# Observability

Agent execution logs should include:

* classification result
* tools used
* retrieved sections
* scoring inputs
* scoring outputs
* final recommendation

---

# Failure Rules

The agent must never:

* fabricate evidence
* invent contract clauses
* hide uncertainty

If retrieval confidence is low, return explicit uncertainty.

---

# MVP Implementation Order

1. repo structure
2. auth
3. document registry
4. document parser
5. document sectioner
6. section storage
7. hybrid retrieval
8. agent orchestrator
9. narrative agent
10. risk agent
11. ROI agent
12. catalog fit agent
13. scoring engine
14. formatters
15. frontend chat
16. tests
17. evals

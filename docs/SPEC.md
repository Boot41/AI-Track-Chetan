# Product Specification

## Product Overview

This application is an internal AI decision-support system for OTT streaming platform executives and analysts.

It helps evaluate whether the platform should:

- greenlight a new original series
- acquire an existing movie catalog
- compare multiple content investment opportunities

The system combines structured PostgreSQL business data with unstructured local documents and AI-driven reasoning to generate:

- a natural-language recommendation
- a structured JSON scorecard
- evidence-backed analysis of risks and opportunities

The application is designed for **internal strategic decision-making**, not for consumer streaming experiences.

---

# Product Goals

The system must enable:

1. **Original Content Evaluation**
   - Analyze scripts, show bibles, budgets, and comparable performance data.

2. **Catalog Acquisition Evaluation**
   - Analyze licensing terms, catalog performance signals, localization costs, and strategic fit.

3. **Investment Comparison**
   - Compare multiple content opportunities and rank them.

4. **Contextual Follow-Up Questions**
   - Allow analysts to ask follow-up questions about earlier evaluations.

5. **Evidence Transparency**
   - Every recommendation must cite supporting document sections and structured data sources.

---

# Core Capabilities

## Narrative & Franchise Parsing

Extract narrative signals from creative materials such as:

- pilot scripts
- show bibles
- pitch decks

Signals include:

- genre
- themes
- tone
- character arcs
- pacing structure
- franchise or spin-off potential

---

## Viewership & ROI Projection

Estimate business performance based on historical platform data.

Outputs include:

- projected completion rate
- expected drop-off risk
- estimated retention lift
- cost per view
- projected ROI

---

## Risk & Contract Analysis

Analyze licensing contracts and content signals for risks.

Examples:

- geographic rights restrictions
- exclusivity windows
- dubbing or localization limitations
- censorship/regulatory risks
- IP ownership issues

---

## Catalog Fit Scoring

Evaluate how well a title fits platform strategy.

Signals include:

- underserved audience segments
- churn-heavy demographics
- genre gaps
- regional demand
- competitor catalog positioning

---

## Structured Decision Output

The agent returns both:

1. Natural-language explanation
2. Structured JSON scorecard

Example scorecard fields:

- projected_completion_rate
- estimated_roi
- catalog_fit_score
- risk_flags
- recommendation
- confidence

---

# System Architecture

The application runs as **three independent services**.

## Client

Location:

```

client/

```

Responsibilities:

- login UI
- chat interface
- scorecard display
- evidence visualization

Must not contain:

- business logic
- scoring formulas
- document reasoning

---

## Backend

Location:

```

server/

```

Responsibilities:

- JWT authentication
- user/session persistence
- protected APIs
- request validation
- routing requests to the agent service

The backend must remain thin.

---

## Agent Service

Location:

```

agent/

```

Responsibilities:

- query understanding
- document retrieval
- SQL retrieval
- narrative analysis
- contract risk analysis
- ROI prediction
- catalog fit scoring
- scorecard generation

The agent service contains the **core intelligence**.

---

# Data Sources

## PostgreSQL

Used for structured data and document indexing.

Expected domains:

- historical viewership metrics
- completion rates
- drop-off metrics
- subscriber demographics
- production budgets
- licensing costs
- localization costs
- competitor catalog metadata

---

## Local Document Repository

Documents are **pre-existing** in the project.

Types include:

- pilot scripts
- show bibles
- pitch decks
- focus group reports
- licensing contracts

No upload feature is required.

---

# Document Processing Requirements

Documents must be processed during ingestion.

## Parsing

Use PyMuPDF for PDFs.

Preserve:

- page numbers
- headings
- clauses
- slide identifiers
- section metadata

---

## Semantic Sectioning

Documents must be split into semantic units.

Examples:

- scripts → scenes
- contracts → clauses
- decks → slides
- reports → sections

---

# Database Requirements

Core document tables:

- `documents`
- `document_sections`
- `document_facts`
- `document_risks`

### documents
Stores source metadata.

### document_sections
Stores retrievable text sections with embeddings.

### document_facts
Stores extracted structured claims. In MVP, this table is populated primarily with contract-derived atomic facts tied to source sections.

### document_risks
Stores detected legal/business risks.

---

# Retrieval Strategy

Hybrid retrieval must be used:

- pgvector embeddings for semantic similarity
- PostgreSQL full-text search for lexical matching
- metadata filtering for narrowing context

Improving retrieval quality is preferred over expanding prompts.

---

# Authentication

Authentication is **JWT-based**.

Rules:

- users must log in before accessing chat
- backend validates JWT
- backend extracts trusted identity such as `user_id` and `session_id`
- backend makes an inter-service call to the standalone agent service
- backend forwards trusted identity and session context to the agent service
- agent service never validates user JWT directly
- agent service must not accept client-originated requests for privileged operations
- agent service trusts backend-forwarded identity only

---

# Output Contract

Every response must include:

```
answer
scorecard
evidence
meta
```

Example shape:

```json
{
  "answer": "This catalog is a strong fit but has territory restrictions.",
  "scorecard": {
    "estimated_roi": 1.32,
    "catalog_fit_score": 78,
    "risk_flags": ["territory_restriction"],
    "recommendation": "conditional_acquire"
  },
  "evidence": [],
  "meta": {
    "warnings": [],
    "confidence": 0.0,
    "review_required": false
  }
}
```

---

# Testing and Evaluation Requirements

Testing must cover the backend, agent service, and frontend.

## Unit Tests

Use `pytest` for:

- parser helpers
- sectioners
- retrieval helpers
- scorers
- formatters
- schema validation
- auth helpers

## Integration Tests

Use `pytest` for:

- document ingestion pipeline
- retrieval and ranking
- backend and agent service communication
- persistence of chat sessions and evaluation results
- backend auth and protected API flows

## End-to-End Tests

Use `Playwright` for:

- login flow
- protected chat access
- chat interaction
- scorecard rendering
- evidence panel rendering

## Agent Evaluation Tests

Use pytest-based eval suites for:

- retrieval grounding
- risk detection accuracy
- recommendation stability
- schema validity
- follow-up conversation handling

---

# MVP Scope

The MVP must include:

* JWT login
* chat interface
* document ingestion
* hybrid retrieval
* narrative analysis
* contract risk detection
* ROI estimation
* catalog fit scoring
* structured scorecard output
* evidence display

---

# Non-Goals

This project does NOT target:

* consumer recommendation engines
* streaming playback
* CMS features
* end-user OTT UX

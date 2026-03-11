# Phase 7 Execution Prompt

## Objective
Complete Phase 7 for this repository with production-safe hardening, eval expansion, operational readiness, and final MVP verification without redesigning architecture boundaries.

## Non-Negotiable Constraints
- Frontend remains thin.
- Backend remains thin.
- Agent service owns retrieval, reasoning, scoring, and recommendation synthesis.
- Preserve stable public response contract:
  - `answer`
  - `scorecard`
  - `evidence`
  - `meta`
- Preserve minimal public `meta` fields:
  - `warnings`
  - `confidence`
  - `review_required`
- Preserve typed contracts and source traceability.

## Required Phase 7 Scope
1. Expand eval corpus and regression coverage.
2. Add regression checks for classification, routing, cache behavior, retrieval grounding, specialist outputs, scorers, formatters, and frontend rendering.
3. Harden failure handling (low confidence, malformed docs, partial ingestion, stale caches, communication failures, weak comparison context, partial valid outputs).
4. Complete operational workflows (reindex behavior, cache invalidation, freshness signaling).
5. Add internal observability for route/classification/tool/retrieval/scorer/recommendation/failure paths.
6. Verify architecture and contract stability.
7. Complete thin end-to-end MVP integration.

## Verification Expectations
- Unit tests
- Integration tests
- Playwright tests
- Eval regression suite execution
- CI readiness for `.github/workflows/ci.yml`

## Completion Notes
- Include changed files.
- Include tests/evals executed.
- State MVP completion status.
- Document residual non-blocking risks.

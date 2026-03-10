# StreamLogic AI Final Revised Roadmap

## Summary

Build StreamLogic AI as three independent services with strict boundaries:

- Thin React frontend for auth, chat, scorecard, and evidence rendering
- Thin FastAPI backend for JWT auth, persistence, validation, and trusted proxying
- Standalone Google ADK agent service for retrieval, reasoning, scoring, and response synthesis

Preserve PostgreSQL as the system of record, use PostgreSQL FTS plus `pgvector` through an explicit fusion-based `HybridRetriever`, and keep the public response contract fixed at:

```json
{
  "answer": "...",
  "scorecard": {},
  "evidence": [],
  "meta": {
    "warnings": [],
    "confidence": 0.0,
    "review_required": false
  }
}
```


## Core Contracts And Defaults

### Public response contract

- `answer`: natural-language recommendation or follow-up response
- `scorecard`: structured evaluation or comparison payload
- `evidence`: evidence items supporting claims
- `meta`: minimal user-facing uncertainty metadata

### Evidence item contract

Each evidence item includes:

- `document_id`
- `section_id`
- `snippet`
- `source_reference`
- `retrieval_method` as `vector | fts | hybrid | sql`
- `confidence_score` as `0.0-1.0`
- `used_by_agent`
- `claim_it_supports`

### Meta contract

Minimum required keys:

- `warnings`
- `confidence`
- `review_required`

All execution, routing, cache, timing, scorer, ingestion, and data-freshness details should be kept in internal logs, persistence records, or debug/admin APIs rather than the user-facing response contract.

### ADK session state

Persist typed session state:

- `pitch_id`
- `query_type`
- `narrative_output`
- `roi_output`
- `risk_output`
- `catalog_output`
- `last_scorecard`
- `retrieval_context`
- `conversation_intent_history`
- `comparison_state`
- `active_option`

`comparison_state` includes:

- `option_a`
- `option_b`
- `comparison_scorecard`
- `comparison_axes`

### Query classification contract

Add an explicit classifier ahead of orchestration:

- `query_type`
- `target_agents`
- `reuse_cached_outputs`
- `requires_recomputation`

Supported query types:

- `original_eval`
- `acquisition_eval`
- `comparison`
- `followup_why_narrative`
- `followup_why_roi`
- `followup_why_risk`
- `followup_why_catalog`
- `scenario_change_budget`
- `scenario_change_localization`
- `general_question`

### Recommendation engine defaults

Implement as deterministic code with configurable weights:

- `narrative_weight = 0.20`
- `roi_weight = 0.30`
- `risk_weight = 0.30`
- `catalog_fit_weight = 0.20`

Override rules:

- Any `BLOCKER` risk forces `PASS`
- Any `HIGH` risk caps recommendation at `CONDITIONAL`

These weights must live in config, not hardcoded business logic scattered across code.

### `document_facts` decision

Implement `document_facts` in MVP only for contract-derived atomic facts. Do not generalize beyond contracts in MVP.

Minimum schema:

- `fact_id`
- `document_id`
- `section_id`
- `subject`
- `predicate`
- `object_value`
- `qualifier`
- `source_text`
- `confidence`
- `extracted_by`

If extraction quality is limited during early implementation, keep `document_facts` as a real table in MVP and populate it only for high-confidence contract-derived facts, rather than replacing it with ad hoc `document_sections` metadata.

## Phased Roadmap

### Phase 0: Foundations, Contracts, Routing Spec, And Golden Fixtures

Tasks:

- Lock service boundaries to thin frontend, thin backend, standalone ADK agent service.
- Define all public and internal typed contracts: response, scorecard, evidence, minimal response meta, session state, query classification, recommendation config, and internal observability models.
- Finalize the `document_facts` MVP scope as contract-only structured facts.
- Define recommendation-engine default weights and override rules with config-based overrides.
- Define the orchestrator routing matrix and follow-up routing rules using the `QueryClassifier`.
- Define comparison-state behavior and active-option targeting rules.
- Define golden fixtures:
  - original-series evaluation
  - acquisition evaluation
  - comparison evaluation
  - follow-up routing cases
  - known contract risk-clause cases
- Create fixture JSON for early frontend rendering and stakeholder feedback.

Dependencies:

- Blocks all implementation.

Testing:

- `pytest` unit tests for schemas and config validation.
- `pytest` integration tests for contract serialization.
- Initial eval tests for query classification, routing expectations, and schema stability.

Suggested branches:

- `feat/foundation-contracts`
- `feat/query-classifier-spec`
- `feat/eval-fixtures`

### Phase 1: Backend Auth, Persistence, And Thin Proxy

Tasks:

- Extend JWT auth into protected chat/session APIs.
- Add persistence for `chat_sessions`, `chat_messages`, and `evaluation_results`.
- Implement backend request validation and response validation against the fixed envelope contract.
- Implement a thin client to the standalone agent service, forwarding only trusted identity and session context.
- Add support for storing and retrieving comparison sessions and evaluation history.
- Add structured logging and internal observability models for routing, cache reuse, scorer execution, timing, ingestion quality, and data freshness.

Dependencies:

- Depends on Phase 0 contracts and DB schema.

Testing:

- `pytest` unit tests for auth helpers, deps, and API schemas.
- `pytest` integration tests for login, protected routes, persistence, mocked agent proxying, and comparison-session persistence.

Suggested branches:

- `feat/backend-auth-sessions`
- `feat/backend-agent-proxy`

### Phase 1.5: Frontend Contract Stub

Tasks:

- Build a fixture-driven frontend shell with:
  - login UI
  - protected layout
  - chat timeline
  - scorecard renderer
  - evidence panel
  - comparison view stub
- Use fixture JSON only, no real API wiring.
- Validate scorecard granularity, evidence presentation, and comparison UX early.

Dependencies:

- Depends on Phase 0 fixture definitions.

Testing:

- Playwright smoke tests for route protection, fixture chat rendering, scorecard rendering, evidence rendering, and comparison fixture rendering.

Suggested branches:

- `feat/frontend-contract-stub`

### Phase 2: Document Ingestion, Structured Parsing, And Hybrid Retrieval

Tasks:

- Build ingestion for pre-existing local documents only.
- Add `DocumentTypeClassifier` and parser routing:
  - `ScriptParser`
  - `ContractParser`
  - `DeckParser`
  - `ReportParser`
- Preserve parser-specific metadata:
  - `scene_id`
  - `clause_id`
  - `parent_clause`
  - `slide_number`
  - section/subsection identifiers
- Extract contract-only `document_facts`.
- Implement explicit ingestion result handling:

`IngestionResult` includes:

- `document_id`
- `status` as `success | partial | failed`
- `sections_indexed`
- `sections_failed`
- `parser_used`
- `ocr_applied`
- `warnings`
- `errors`
- `fallback_applied`

- Define parser fallback behavior:
  - contracts: paragraph fallback with low structure confidence
  - scripts: page-level fallback
  - decks: OCR fallback, then manual-review warning if extraction remains weak
- Implement `HybridRetriever`:
  - FTS retrieval
  - vector retrieval
  - RRF fusion
  - per-document-type weighting
  - reranking
  - result confidence
- Carry ingestion warnings into downstream evidence and convert user-relevant uncertainty into minimal response `meta` fields.

Dependencies:

- Depends on Phase 0 schemas and DB design.

Testing:

- `pytest` unit tests for parsers, sectioners, fallback logic, fact extraction, fusion, and reranking.
- `pytest` integration tests for ingestion success, partial failure, failed ingestion, indexing, retrieval quality, and provenance.
- Eval tests for contract-clause recall, low-structure-confidence handling, and script-scene retrieval.

Suggested branches:

- `feat/document-parser`
- `feat/document-facts-contracts`
- `feat/hybrid-retriever`

### Phase 3: ADK Orchestrator, QueryClassifier, And Tool Layer

Tasks:

- Replace the scaffold agent with:
  - explicit `QueryClassifier`
  - root ADK orchestrator
  - typed subagent interfaces
- Implement ADK tools for:
  - SQL retrieval
  - hybrid document retrieval
  - clause extraction
  - narrative feature extraction
  - evidence packaging
- Enforce deterministic routing using the classifier output.

Routing defaults:

- `original_eval`: Narrative -> ROI -> Risk -> Catalog -> recommendation
- `acquisition_eval`: Risk + Catalog -> ROI -> recommendation
- `comparison`: run evaluation pipeline per option, then synthesize comparison
- `followup_why_narrative`: Narrative only using cached outputs as context
- `followup_why_roi`: ROI only, explanation-first unless recomputation required
- `followup_why_risk`: Risk only, retrieve clauses/regulatory support
- `followup_why_catalog`: Catalog only, compare against prior gaps/benchmarks
- `scenario_change_budget`: rerun ROI and recommendation
- `scenario_change_localization`: rerun ROI, Catalog, and recommendation

- Log `routing_decision` and cache reuse in internal observability records, not response `meta`.

Dependencies:

- Depends on Phase 2 retrieval and Phase 0 classifier/session contracts.

Testing:

- `pytest` unit tests for classifier behavior and tool interfaces.
- `pytest` integration tests for each query type and cache-reuse pattern.
- Eval tests for follow-up routing, scenario-change routing, and comparison targeting.

Suggested branches:

- `feat/query-classifier`
- `feat/agent-orchestrator`
- `feat/agent-tools-core`

### Phase 4: Specialist Subagents And Deterministic Scorers

Tasks:

- Implement Document Retrieval Agent.
- Implement Narrative Analysis Agent.
- Implement ROI Prediction Agent.
- Implement Risk & Contract Analysis Agent.
- Implement Catalog Fit Agent.
- Implement pure deterministic scorers:
  - `completion_rate_scorer`
  - `roi_scorer`
  - `catalog_fit_scorer`
  - `risk_severity_scorer`
  - `recommendation_engine`
- Make subagents produce typed scoring inputs, not final opaque scores from prompts.
- Make the recommendation engine the single deterministic synthesis point.

Dependencies:

- Depends on Phase 3 interfaces and Phase 2 retrieval quality.

Testing:

- `pytest` unit tests for all scorers and typed outputs.
- `pytest` integration tests for orchestrator + subagents + scorers.
- Eval tests for recommendation stability, comparable-title grounding, risk accuracy, and comparison consistency.

Suggested branches:

- `feat/narrative-agent`
- `feat/roi-agent`
- `feat/risk-agent`
- `feat/catalog-fit-agent`
- `feat/scoring-engine`

### Phase 5: Formatting, Uncertainty, And Contract Enforcement

Tasks:

- Implement formatter modules for answer text, scorecard normalization, evidence formatting, and comparison response formatting.
- Use evidence confidence plus ingestion warnings to drive explicit uncertainty wording.
- Surface user-relevant uncertainty in response `meta.warnings`, `meta.confidence`, and `meta.review_required`.
- Support partial scorecard updates for follow-up turns without breaking the top-level envelope.
- Persist evidence references, scorer invocations, cache hits, route metadata, ingestion quality, and timing in internal records.

Dependencies:

- Depends on Phase 4 outputs.

Testing:

- `pytest` unit tests for formatter rules and uncertainty thresholds.
- `pytest` integration tests for backend-agent contract enforcement and persistence.
- Eval tests for schema stability, traceability, and honesty under low-confidence conditions.

Suggested branches:

- `feat/response-formatters`
- `feat/backend-agent-integration`

### Phase 6: Real Frontend Integration

Tasks:

- Replace fixture-backed behavior with real backend integration.
- Implement authenticated chat, session history, scorecard rendering, evidence display, and comparison workflow using only validated backend responses.
- Keep frontend display-only.
- Support follow-up turns and comparison follow-ups using backend-provided session context.
- Add progressive enhancements only after the core flow is stable.

Dependencies:

- Depends on Phases 1, 5, and findings from Phase 1.5.

Testing:

- Playwright tests for login, live evaluation, follow-up questions, comparison flow, scorecard rendering, and evidence rendering.

Suggested branches:

- `feat/frontend-chat-scorecard`
- `feat/frontend-comparison-view`

### Phase 7: Operational Readiness, Data Refresh, And Hardening

Tasks:

- Expand the eval corpus from Phase 0 into a regression suite.
- Define competitor catalog refresh workflow:
  - source mechanism for MVP
  - validation rules
  - refresh cadence
  - import timestamping
  - staleness captured in internal observability and surfaced to users only when it affects `warnings`, `confidence`, or `review_required`
- Define document reindex workflow:
  - trigger rules
  - replace vs append semantics
  - cache invalidation behavior when section IDs or clause IDs change
- Validate failure modes for:
  - stale competitor data
  - malformed documents
  - low-confidence retrieval
  - stale session cache after reindex
  - backend-agent communication failure
- Perform architecture review to ensure frontend/backend remain thin and the agent service owns all intelligence.

Dependencies:

- Depends on all prior phases.

Testing:

- Full `pytest` unit suite
- Full `pytest` integration suite
- Full Playwright suite
- Full eval suite for retrieval, routing, comparison, determinism, grounding, and follow-up handling

Suggested branches:

- `feat/evals-suite`
- `feat/operational-data-workflows`
- `feat/observability-hardening`

## Dependency Map

Critical path:

1. Contracts, classifier spec, recommendation config, and golden fixtures
2. Backend auth and persistence
3. Structured ingestion and hybrid retrieval
4. QueryClassifier, orchestrator, and tool layer
5. Specialist subagents and deterministic scorers
6. Formatters and contract enforcement
7. Real frontend integration
8. Operational hardening and expanded evals

Parallelizable work:

- Frontend contract stub can start after Phase 0.
- Some scorer implementation can start once Phase 0 weights and typed subagent outputs are fixed.
- Operational workflow design can begin earlier, but execution stays late.

## Assumptions And Defaults

- Repo docs remain authoritative over alternate architectures.
- PostgreSQL with FTS and `pgvector` is the required retrieval substrate.
- Documents are pre-existing local files; upload flows are out of MVP.
- The agent service remains standalone and backend-trusted.
- `document_facts` is contract-only in MVP.
- Recommendation weights are configurable defaults, not immutable business truth.
- Streaming remains optional and secondary to architecture correctness.

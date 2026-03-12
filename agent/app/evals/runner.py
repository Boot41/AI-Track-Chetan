from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.agents.orchestrator import AgentOrchestrator
from app.evals.judge import SemanticJudge
from app.evals.metrics import calculate_precision_at_k, calculate_recall_at_k
from app.formatters import format_public_response
from app.schemas.eval_runner import (
    CaseEvalResult,
    EvalBehavior,
    EvalCase,
    EvalSuiteResult,
)
from app.schemas.orchestration import AgentRequest, SessionState, TrustedRequestContext

logger = logging.getLogger(__name__)


class MockJudge:
    async def judge(self, query: str, answer: str, **kwargs: Any) -> Any:
        from app.evals.judge import JudgeResponse
        from app.schemas.eval_runner import JudgeScore

        return JudgeResponse(
            faithfulness=JudgeScore(score=4, rationale="Mock rationale: appears faithful."),
            helpfulness=JudgeScore(score=4, rationale="Mock rationale: appears helpful."),
        )


class EvalRunner:
    def __init__(
        self,
        orchestrator: AgentOrchestrator,
        judge: SemanticJudge | Any | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.judge = judge or MockJudge()

    async def run_suite(self, fixture_paths: list[Path]) -> EvalSuiteResult:
        cases = self.load_cases(fixture_paths)
        results = []
        for case in cases:
            result = await self.run_case(case)
            results.append(result)

        return self.aggregate_results(results)

    def load_cases(self, fixture_paths: list[Path]) -> list[EvalCase]:
        cases = []
        for path in fixture_paths:
            if path.is_dir():
                for f in path.rglob("*.json"):
                    cases.extend(self._load_from_path(f))
            else:
                cases.extend(self._load_from_path(path))
        return cases

    def _load_from_path(self, path: Path) -> list[EvalCase]:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return [self._validate_case(item, f"{path.stem}_{i}") for i, item in enumerate(data)]
        else:
            return [self._validate_case(data, path.stem)]

    def _validate_case(self, data: dict[str, Any], default_id: str) -> EvalCase:
        # Basic migration/backward compatibility for old fixtures
        if "fixture_id" not in data:
            data["fixture_id"] = default_id

        # Mapping old query_type to behavior or adding defaults
        if "expected_classification" in data and "behavior" not in data:
            data["behavior"] = EvalBehavior.DETERMINISTIC_PASS

        return EvalCase.model_validate(data)

    async def run_case(self, case: EvalCase) -> CaseEvalResult:
        logger.info(f"Running case: {case.fixture_id}")
        failure_reasons = []

        # 1. Run primary query
        request = AgentRequest(
            message=case.query,
            context=TrustedRequestContext(user_id=1, session_id=case.fixture_id),
            session_state=SessionState(pitch_id=case.pitch_id),
        )

        orchestration_result = await self.orchestrator.orchestrate(request)
        public_response = format_public_response(orchestration_result)

        # 2. Check Behavior
        if case.behavior == EvalBehavior.UNCERTAINTY:
            if not public_response["meta"]["review_required"]:
                failure_reasons.append("Expected review_required but got False")
            if not public_response["meta"]["warnings"]:
                failure_reasons.append("Expected warnings but got none")

        # 3. Retrieval Metrics
        retrieved_evidence = public_response["evidence"]
        recall = calculate_recall_at_k(retrieved_evidence, case.required_evidence)
        # Precision@5 needs labels; using section_ids of required_evidence as proxies
        relevant_labels = [r.section_id for r in case.required_evidence if r.section_id]
        precision = calculate_precision_at_k(
            retrieved_evidence, relevant_labels if relevant_labels else None
        )

        # 4. LLM-as-a-Judge
        faithfulness = None
        helpfulness = None
        if self.judge:
            judge_res = await self.judge.judge(
                query=case.query,
                answer=public_response["answer"],
                golden_answer=case.golden_answer,
                expected_risks=case.expected_key_risks,
                expected_facts=case.expected_roi_facts,
            )
            faithfulness = judge_res.faithfulness
            helpfulness = judge_res.helpfulness

            if faithfulness.score < 3:
                failure_reasons.append(f"Faithfulness score too low: {faithfulness.score}")
            if helpfulness.score < 3:
                failure_reasons.append(f"Helpfulness score too low: {helpfulness.score}")

        # 5. Sensitivity (if config perturbations exist)
        sensitivity_results = []
        for i, perturbed_config in enumerate(case.config_perturbations):
            logger.info(f"Running sensitivity test {i+1} for {case.fixture_id}")
            perturbed_request = AgentRequest(
                message=case.query,
                context=TrustedRequestContext(user_id=1, session_id=f"{case.fixture_id}_s{i}"),
                session_state=SessionState(pitch_id=case.pitch_id),
                recommendation_config=perturbed_config,
            )
            perturbed_result = await self.orchestrator.orchestrate(perturbed_request)

            # Compare outcomes and scores
            orig_rec = orchestration_result.recommendation_result
            pert_rec = perturbed_result.recommendation_result

            original_outcome = orig_rec.outcome if orig_rec else None
            perturbed_outcome = pert_rec.outcome if pert_rec else None

            original_score = orig_rec.weighted_score if orig_rec else None
            perturbed_score = pert_rec.weighted_score if pert_rec else None

            sensitivity_results.append(
                {
                    "config_index": i,
                    "original_outcome": original_outcome,
                    "perturbed_outcome": perturbed_outcome,
                    "outcome_changed": original_outcome != perturbed_outcome,
                    "original_score": original_score,
                    "perturbed_score": perturbed_score,
                    "score_delta": (
                        (perturbed_score - original_score)
                        if perturbed_score is not None and original_score is not None
                        else None
                    ),
                }
            )

        # 6. Multi-turn (if sequence exists)
        multi_turn_results = []
        current_state = self.orchestrator.update_session_state(
            request.session_state, orchestration_result
        )
        for turn_query in case.multi_turn_sequence:
            turn_request = AgentRequest(
                message=turn_query,
                context=request.context,
                session_state=current_state,
            )
            turn_result = await self.orchestrator.orchestrate(turn_request)
            turn_public = format_public_response(turn_result)
            passed_turn = (
                not turn_public["meta"]["review_required"]
                if case.behavior != EvalBehavior.UNCERTAINTY
                else True
            )
            multi_turn_results.append(
                {"query": turn_query, "answer": turn_public["answer"], "passed": passed_turn}
            )
            current_state = self.orchestrator.update_session_state(current_state, turn_result)

        passed = len(failure_reasons) == 0
        return CaseEvalResult(
            fixture_id=case.fixture_id,
            passed=passed,
            faithfulness=faithfulness,
            helpfulness=helpfulness,
            recall_at_5=recall,
            precision_at_5=precision,
            failure_reasons=failure_reasons,
            sensitivity_results=sensitivity_results,
            multi_turn_results=multi_turn_results,
            is_adversarial=case.is_adversarial,
            has_multi_turn=len(case.multi_turn_sequence) > 0,
        )

    def aggregate_results(self, results: list[CaseEvalResult]) -> EvalSuiteResult:
        total = len(results)
        passed_count = sum(1 for r in results if r.passed)

        faithfulness_scores = [r.faithfulness.score for r in results if r.faithfulness]
        helpfulness_scores = [r.helpfulness.score for r in results if r.helpfulness]
        recalls = [r.recall_at_5 for r in results if r.recall_at_5 is not None]
        precisions = [r.precision_at_5 for r in results if r.precision_at_5 is not None]

        adversarial_cases = [r for r in results if getattr(r, "is_adversarial", False)]
        adv_passed = sum(1 for r in adversarial_cases if r.passed)
        adversarial_pass_rate = adv_passed / len(adversarial_cases) if adversarial_cases else None

        multiturn_cases = [r for r in results if getattr(r, "has_multi_turn", False)]
        mt_passed = sum(
            1 for r in multiturn_cases if all(m["passed"] for m in r.multi_turn_results)
        )
        multiturn_consistency_pass_rate = mt_passed / len(multiturn_cases) if multiturn_cases else None

        # Sensitivity Summary
        sensitivity_cases = [r for r in results if r.sensitivity_results]
        total_perturbations = sum(len(r.sensitivity_results) for r in sensitivity_cases)
        total_outcome_changes = sum(
            sum(1 for s in r.sensitivity_results if s["outcome_changed"])
            for r in sensitivity_cases
        )
        config_sensitivity_summary = {
            "total_sensitivity_cases": len(sensitivity_cases),
            "total_perturbations_run": total_perturbations,
            "outcome_changed_count": total_outcome_changes,
            "outcome_stability_rate": (
                1 - (total_outcome_changes / total_perturbations)
                if total_perturbations > 0
                else 1.0
            ),
        }

        return EvalSuiteResult(
            total_cases=total,
            pass_rate=passed_count / total if total > 0 else 0,
            avg_faithfulness=(
                sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else None
            ),
            avg_helpfulness=(
                sum(helpfulness_scores) / len(helpfulness_scores) if helpfulness_scores else None
            ),
            recall_at_5=sum(recalls) / len(recalls) if recalls else None,
            precision_at_5=sum(precisions) / len(precisions) if precisions else None,
            adversarial_pass_rate=adversarial_pass_rate,
            multiturn_consistency_pass_rate=multiturn_consistency_pass_rate,
            config_sensitivity_summary=config_sensitivity_summary,
            per_case_details=results,
        )

    def print_summary(self, result: EvalSuiteResult):
        print("\n" + "=" * 50)
        print("EVALUATION SUMMARY")
        print("=" * 50)
        print(f"Total Cases: {result.total_cases}")
        print(f"Pass Rate:   {result.pass_rate:.2%}")
        if result.avg_faithfulness:
            print(f"Avg Faithfulness: {result.avg_faithfulness:.2f}/5")
        if result.avg_helpfulness:
            print(f"Avg Helpfulness:  {result.avg_helpfulness:.2f}/5")
        if result.recall_at_5:
            print(f"Recall@5:         {result.recall_at_5:.2%}")
        if result.adversarial_pass_rate is not None:
            print(f"Adversarial Pass Rate: {result.adversarial_pass_rate:.2%}")
        if result.multiturn_consistency_pass_rate is not None:
            print(f"Multi-turn Pass Rate:  {result.multiturn_consistency_pass_rate:.2%}")
        print("=" * 50)

        for case in result.per_case_details:
            status = "PASS" if case.passed else "FAIL"
            print(f"[{status}] {case.fixture_id}")
            if not case.passed:
                for reason in case.failure_reasons:
                    print(f"  - {reason}")
        print("=" * 50 + "\n")


async def main():
    import argparse

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    parser = argparse.ArgumentParser(description="StreamLogic Agent Evaluation Runner")
    parser.add_argument(
        "--fixtures", type=str, default="agent/app/evals/fixtures", help="Path to fixtures"
    )
    parser.add_argument(
        "--output", type=str, default="eval_results.json", help="Path to output JSON results"
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default="postgresql+asyncpg://postgres:postgres@localhost:5433/app_scaffold_test",
        help="Database URL for orchestrator",
    )

    args = parser.parse_args()

    engine = create_async_engine(args.db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    orchestrator = AgentOrchestrator(session_factory)
    # In a real run, we might want a real judge or a mock judge depending on ENV
    runner = EvalRunner(orchestrator)

    fixture_path = Path(args.fixtures)
    result = await runner.run_suite([fixture_path])

    runner.print_summary(result)

    with open(args.output, "w") as f:
        f.write(result.model_dump_json(indent=2))
    print(f"Full results saved to {args.output}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

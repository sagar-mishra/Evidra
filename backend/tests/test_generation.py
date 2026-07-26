"""
Milestone 4 validation script — Configurable AI Test Generation.

Instantiates the local LiteLLM + Instructor generator, passes a mock PLC
change and requirement, and prints the validated RegressionTestSchema JSON.

Usage (from project root):
    uv run python backend/tests/test_generation.py

Prerequisites:
    - Ollama (or vLLM) running locally, default http://localhost:11434
    - A chat model pulled, e.g. `ollama pull llama3.1`
    - Optional env overrides:
        LLM_MODEL=ollama/llama3.1
        LLM_API_BASE=http://localhost:11434
"""

from __future__ import annotations

import json
import sys

from app.ai.llm_generator import LLMGeneratorError, RegressionTestGenerator
from app.schemas.tests import RegressionTestSchema, TestCategory

# Mock inputs (Milestone 4 validation gate)
MOCK_TAG_CHANGE = "T_F2S_P101 changed from 10000 to 30000"
MOCK_REQUIREMENT = "Pump 101 fail-to-start timeout"
MOCK_EQUIPMENT = ["PUMP101"]
MOCK_TAGS = ["T_F2S_P101", "ALM_PUMP101_FailToStart"]


def _divider(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _validate_required_fields(plan: RegressionTestSchema) -> list[str]:
    failures: list[str] = []
    if not plan.affected_equipment:
        failures.append("affected_equipment is empty")
    if plan.category is None:
        failures.append("category is missing")
    if not plan.prerequisites:
        failures.append("prerequisites is empty")
    if not plan.test_steps:
        failures.append("test_steps is empty")
    if not (plan.expected_result or "").strip():
        failures.append("expected_result is empty")
    return failures


def main() -> None:
    print("Milestone 4 — Configurable AI Test Generation (LiteLLM + Instructor)")
    generator = RegressionTestGenerator()
    print(f"Model    : {generator.model}")
    print(f"API base : {generator.api_base}")
    print(f"Mode     : Instructor JSON → RegressionTestSchema")

    _divider("INPUT")
    print(f"Tag change : {MOCK_TAG_CHANGE}")
    print(f"Requirement: {MOCK_REQUIREMENT}")
    print(f"Equipment  : {MOCK_EQUIPMENT}")
    print(f"Tags       : {MOCK_TAGS}")

    _divider("LLM GENERATION")
    try:
        plan = generator.generate_regression_test(
            tag_change=MOCK_TAG_CHANGE,
            requirement=MOCK_REQUIREMENT,
            affected_equipment=MOCK_EQUIPMENT,
            related_tags=MOCK_TAGS,
            category_hint=TestCategory.ALARMS_TIMERS,
        )
    except LLMGeneratorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "\nTroubleshooting:\n"
            "  1. Start Ollama:  ollama serve\n"
            "  2. Pull a model:  ollama pull llama3.1\n"
            "  3. Override model: set LLM_MODEL=ollama/<your-model>\n"
            "  4. Override URL:  set LLM_API_BASE=http://localhost:11434",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    _divider("STRUCTURED REGRESSION TEST (JSON)")
    print(plan.model_dump_json(indent=2))

    failures = _validate_required_fields(plan)
    _divider("VALIDATION")
    if failures:
        print("FAILED schema field checks:")
        for item in failures:
            print(f"  - {item}")
        print(json.dumps({"status": "FAIL", "failures": failures}, indent=2))
        raise SystemExit(1)

    print(
        json.dumps(
            {
                "status": "OK",
                "test_id": plan.test_id,
                "title": plan.title,
                "category": plan.category.value,
                "affected_equipment": plan.affected_equipment,
                "prerequisites_count": len(plan.prerequisites),
                "test_steps_count": len(plan.test_steps),
                "expected_result_preview": plan.expected_result[:160],
                "model": generator.model,
                "schema": "RegressionTestSchema",
            },
            indent=2,
        )
    )
    print("\nAll Milestone 4 generation checks PASSED.")
    print("Milestone 4 AI test generation completed successfully.")


if __name__ == "__main__":
    main()

"""
Dual-model LLM service for PLC release review.

- Fast model (``LLM_MODEL_NAME``): lightweight formatting / legacy drafts
- Reasoning model (``LLM_REASONING_MODEL``): StrictFinding / constrained evaluation

Providers (LiteLLM + Instructor): anthropic (default) | openai | gemini | ollama | vllm
"""

from __future__ import annotations

import json
import os
from typing import Any

import instructor
from instructor import Mode
from litellm import completion
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.findings import (
    ConstrainedFinding,
    RequirementMapping,
    StrictFindingSchema,
    StructuredPlcChange,
)
from app.schemas.tests import (
    GenerateTestRequest,
    RegressionTestSchema,
    TestCategory,
    TestStep,
)

STRICT_SYSTEM_PROMPT = """\
You are assisting a controls engineer with PLC release review. You must only use \
the structured facts and industrial rules supplied below. Do not invent programmer \
intent. Do not claim that the PLC is safe or unsafe.

You MUST populate these five behavioral fields:
1. required_behavior — what the SOO says must happen
2. verified_code_change — exact instruction/tag that changed (facts only)
3. predicted_revised_behavior — what revised logic is likely to do (from rules only)
4. test_pass_condition — behavior required for the regression test to pass
5. predicted_test_outcome — one of PASS | FAIL | UNKNOWN

Also set:
- engineering_disposition: CONFIRM FINDING | DISMISS | NEEDS INVESTIGATION
- uncertainty: Verified | High confidence | Probable | Unknown
- classification: Approved change | Suspected regression | Needs review

Never describe an AFI as implementing new operating functionality.
AFI always evaluates false and disables the downstream rung path.
Ensure regression test prerequisites explicitly state running in simulation or an \
approved FAT environment (do not test on a live field PLC).

Output MUST match the provided JSON schema exactly. No markdown, no prose outside fields.
"""

LEGACY_SYSTEM_PROMPT = """\
You are a senior industrial controls QA engineer preparing focused Factory
Acceptance Test (FAT) regression procedures for Rockwell PLC projects.
Output MUST conform exactly to the provided JSON schema.
Never invent PLC logic not supported by the supplied change and requirement.
Tests are READ-ONLY advisory procedures. Do not claim the release is safe.
Prerequisites must require simulation or an approved FAT environment.
"""


class LLMGeneratorError(RuntimeError):
    """Raised when LLM generation or schema validation fails."""


class RegressionTestGenerator:
    """
    Dual-model LLM service:

    - ``self.model`` / ``LLM_MODEL_NAME`` → fast tasks
    - ``self.reasoning_model`` / ``LLM_REASONING_MODEL`` → StrictFinding eval
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        mode: Mode | None = None,
        provider: str | None = None,
        reasoning_model: str | None = None,
    ) -> None:
        # Provider may already be fallback-resolved in settings (anthropic → openai/gemini)
        self.provider = (provider or settings.LLM_PROVIDER).lower()
        # Fast model
        self.model = model or settings.resolve_litellm_model(reasoning=False)
        # Complex reasoning model (StrictFindingSchema)
        self.reasoning_model = reasoning_model or settings.resolve_litellm_model(
            reasoning=True
        )
        resolved_base = (
            api_base if api_base is not None else settings.resolve_llm_api_base()
        )
        self.api_base = resolved_base.rstrip("/") if resolved_base else None
        self.api_key = (
            api_key if api_key is not None else settings.resolve_llm_api_key()
        )
        self.temperature = (
            settings.LLM_TEMPERATURE if temperature is None else temperature
        )
        self.max_tokens = (
            settings.LLM_MAX_TOKENS if max_tokens is None else max_tokens
        )

        if mode is not None:
            self._mode = mode
        elif self.provider in {"openai", "anthropic"}:
            # TOOLS / function-calling works well for OpenAI + Anthropic via LiteLLM
            self._mode = Mode.TOOLS
        elif self.provider == "gemini":
            self._mode = Mode.JSON
        else:
            self._mode = Mode.JSON

        self._ensure_provider_env()
        self._client = instructor.from_litellm(completion, mode=self._mode)

    def _ensure_provider_env(self) -> None:
        """
        Ensure LiteLLM can see provider credentials in the process environment.

        Priority: when LLM_PROVIDER=anthropic, always set ANTHROPIC_API_KEY from settings.
        """
        if self.provider == "anthropic":
            key = (self.api_key or settings.ANTHROPIC_API_KEY or "").strip()
            if key:
                # Explicit assign (not setdefault) so container env reloads take effect
                os.environ["ANTHROPIC_API_KEY"] = key
                self.api_key = key
        elif self.provider == "openai":
            key = (self.api_key or settings.OPENAI_API_KEY or "").strip()
            if key:
                os.environ["OPENAI_API_KEY"] = key
                self.api_key = key
        elif self.provider == "gemini":
            key = (self.api_key or settings.GEMINI_API_KEY or "").strip()
            if key:
                os.environ["GEMINI_API_KEY"] = key
                os.environ["GOOGLE_API_KEY"] = key
                self.api_key = key

    def _require_api_key(self) -> None:
        cloud = {"anthropic", "openai", "gemini"}
        if self.provider not in cloud:
            return
        if self.api_key and str(self.api_key).strip():
            return
        key_names = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }
        raise LLMGeneratorError(
            f"{key_names[self.provider]} is required when LLM_PROVIDER={self.provider}."
        )

    def _completion_kwargs(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_model: type,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "response_model": response_model,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        return kwargs

    # ------------------------------------------------------------------
    # Primary: constrained finding (REASONING model)
    # ------------------------------------------------------------------

    def generate_constrained_finding(
        self,
        change: StructuredPlcChange | dict[str, Any],
        applied_rules: list[dict[str, str]],
        requirement: RequirementMapping | dict[str, Any],
    ) -> ConstrainedFinding:
        """
        Final controls-engineering evaluation using ``LLM_REASONING_MODEL``
        (StrictFindingSchema / ConstrainedFinding).

        Defaults: anthropic/claude-3-5-sonnet-20240620 (or OpenAI/Gemini fallbacks).
        """
        self._require_api_key()
        # Re-assert env keys immediately before the call (Azure cold start safety)
        self._ensure_provider_env()

        change_obj = (
            change
            if isinstance(change, StructuredPlcChange)
            else StructuredPlcChange.model_validate(change)
        )
        req_obj = (
            requirement
            if isinstance(requirement, RequirementMapping)
            else RequirementMapping.model_validate(requirement)
        )

        user_content = (
            f"Structured PLC change:\n{change_obj.model_dump_json(indent=2)}\n\n"
            f"Industrial rules applied:\n{json.dumps(applied_rules, indent=2)}\n\n"
            f"Candidate SOO requirement:\n{req_obj.model_dump_json(indent=2)}\n\n"
            "Using ONLY the facts and rules above, produce the structured finding.\n"
            "Fill required_behavior, verified_code_change, predicted_revised_behavior, "
            "test_pass_condition, predicted_test_outcome.\n"
            "Also fill verified_change (= verified_code_change), "
            "likely_behavioral_impact (= predicted_revised_behavior), "
            "requirement_relationship (how change relates to SOO).\n"
            "Never describe an AFI as new operating functionality. "
            "Prerequisites must require simulation or an approved FAT environment."
        )

        try:
            # Explicitly use reasoning model for StrictFindingSchema evaluation
            result: StrictFindingSchema = self._client.chat.completions.create(
                **self._completion_kwargs(
                    model=self.reasoning_model,
                    messages=[
                        {"role": "system", "content": STRICT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    response_model=StrictFindingSchema,
                    temperature=min(self.temperature, 0.2),
                )
            )
        except ValidationError as exc:
            raise LLMGeneratorError(
                f"LLM output failed Pydantic validation: {exc}"
            ) from exc
        except Exception as exc:
            raise LLMGeneratorError(
                f"Constrained reasoning failed "
                f"(provider={self.provider}, model={self.reasoning_model}): {exc}"
            ) from exc

        if not isinstance(result, ConstrainedFinding):
            raise LLMGeneratorError(
                f"Unexpected generator return type: {type(result)!r}"
            )
        return result

    def finding_to_regression_schema(
        self,
        finding: ConstrainedFinding,
        *,
        change: StructuredPlcChange,
        requirement: RequirementMapping,
    ) -> RegressionTestSchema:
        """Map constrained finding → RegressionTestSchema for the existing UI."""
        class_map = {
            "Approved change": TestCategory.GENERAL,
            "Suspected regression": TestCategory.INTERLOCK,
            "Needs review": TestCategory.GENERAL,
        }
        category = class_map.get(finding.classification, TestCategory.GENERAL)
        equipment: list[str] = []
        if change.equipment:
            equipment.append(change.equipment)
        for t in change.output_tags:
            if t not in equipment:
                equipment.append(t)
        if not equipment:
            equipment = ["System"]

        flag_rationale = (
            f"{finding.verified_code_change or finding.verified_change} "
            f"{finding.predicted_revised_behavior or finding.likely_behavioral_impact} "
            f"{finding.requirement_relationship}"
        ).strip()

        return RegressionTestSchema(
            test_id=f"TC-{change.change_id or 'GEN'}",
            title=finding.test_title,
            affected_equipment=equipment[:8],
            category=category,
            change_class=None,
            related_tags=list(
                dict.fromkeys(
                    [*(change.output_tags or []), *(change.input_tags or [])]
                )
            )[:20],
            governing_requirement=requirement.requirement_text[:500],
            change_summary=finding.verified_change[:500],
            purpose=finding.likely_behavioral_impact[:500],
            prerequisites=finding.test_prerequisites,
            test_steps=[
                TestStep(step_number=i, action=step, observation=None)
                for i, step in enumerate(finding.test_steps, start=1)
            ],
            expected_result=finding.expected_result,
            flag_rationale=flag_rationale[:2000],
            evidence_to_capture=[
                "PLC watch values",
                "Logic trace",
                "Requirement citation",
            ],
            safety_notes=[
                "Simulation or approved FAT only — do not test on a live field PLC.",
                *([f"Unknown: {u}" for u in finding.unknowns[:5]]),
            ],
        )

    # ------------------------------------------------------------------
    # Fast model: lightweight / legacy drafts (LLM_MODEL_NAME)
    # ------------------------------------------------------------------

    def generate_regression_test(
        self,
        tag_change: str,
        requirement: str,
        *,
        affected_equipment: list[str] | None = None,
        related_tags: list[str] | None = None,
        category_hint: TestCategory | str | None = None,
    ) -> RegressionTestSchema:
        """Lightweight draft using LLM_MODEL_NAME (fast model)."""
        self._require_api_key()
        tag_change = (tag_change or "").strip()
        requirement = (requirement or "").strip()
        if not tag_change:
            raise LLMGeneratorError("tag_change must not be empty")
        if not requirement:
            raise LLMGeneratorError("requirement must not be empty")

        user_prompt = self._build_legacy_user_prompt(
            tag_change=tag_change,
            requirement=requirement,
            affected_equipment=affected_equipment,
            related_tags=related_tags,
            category_hint=category_hint,
        )

        try:
            result: RegressionTestSchema = self._client.chat.completions.create(
                **self._completion_kwargs(
                    model=self.model,  # FAST model
                    messages=[
                        {"role": "system", "content": LEGACY_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_model=RegressionTestSchema,
                )
            )
        except ValidationError as exc:
            raise LLMGeneratorError(
                f"LLM output failed Pydantic validation: {exc}"
            ) from exc
        except Exception as exc:
            raise LLMGeneratorError(
                f"Fast LLM generation failed "
                f"(provider={self.provider}, model={self.model}): {exc}"
            ) from exc

        return result

    def generate_from_request(self, request: GenerateTestRequest) -> RegressionTestSchema:
        return self.generate_regression_test(
            tag_change=request.tag_change,
            requirement=request.requirement,
            affected_equipment=request.affected_equipment,
            related_tags=request.related_tags,
            category_hint=request.category_hint,
        )

    @staticmethod
    def _build_legacy_user_prompt(
        *,
        tag_change: str,
        requirement: str,
        affected_equipment: list[str] | None,
        related_tags: list[str] | None,
        category_hint: Any,
    ) -> str:
        lines = [
            "Draft one focused regression test plan.",
            f"PLC CHANGE:\n{tag_change}",
            f"GOVERNING REQUIREMENT:\n{requirement}",
            "Prerequisites must include simulation or approved FAT environment.",
            "Populate flag_rationale (2–4 sentences).",
        ]
        if affected_equipment:
            lines.append("EQUIPMENT: " + ", ".join(affected_equipment))
        if related_tags:
            lines.append("TAGS: " + ", ".join(related_tags))
        if category_hint is not None:
            hint = (
                category_hint.value
                if hasattr(category_hint, "value")
                else str(category_hint)
            )
            lines.append(f"CATEGORY: {hint}")
        return "\n".join(lines)


def get_default_generator() -> RegressionTestGenerator:
    return RegressionTestGenerator()

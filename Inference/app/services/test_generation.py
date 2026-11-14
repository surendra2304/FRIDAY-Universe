"""Automated Test Generation Service for FORGE."""

import ast
import asyncio
import time
from typing import Literal

from pydantic import BaseModel, Field

from app.services.code_generation import extract_code
from app.utils.logger import logger

from app.providers.unified_manager import (
    UnifiedExecutionRequest,
    unified_provider_manager,
)

# TASK-REL-026: test generation used to make ONE unified-manager call on the
# test_generator role's primary model (gemini / gemini-flash-latest) inside
# the gateway's chat-scale request deadline (REQUEST_TIMEOUT 60s, of which
# the primary provider only sees PRIMARY_ATTEMPT_FRACTION). A single Gemini
# timeout under provider strain therefore produced an empty suite, which
# the endpoint then reported as HTTP 200 with generation_status="degraded"
# — and Forge's verification gate failed good code for an infrastructure
# reason (TASK-REL-023 live evidence, 2026-11-14: "gemini: TimeoutError").
#
# Generation is now a bounded sequence of attempts across the role's
# DECLARED provider/model configs, each with a per-attempt wall-clock
# budget sized to the task (an 8000-token suite is a much bigger job than
# a chat answer). One provider's timeout, degradation or unusable output
# fails only that attempt, never the request.
ATTEMPT_TIMEOUT_SECONDS = 75.0

# Fallback attempt sequence, mirroring the test_generator agent's
# registered model configs (app/agents/software_specialists.py). Used only
# when the registry has no test_generator entry (e.g. bare test imports).
# TASK-REL-021 verified live that Groq serves openai/gpt-oss-120b and
# qwen/qwen3.8-27b, so attempts 2-3 are known-good routes, not guesses.
DEFAULT_ATTEMPT_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("gemini", "gemini-flash-latest"),
    ("groq", "openai/gpt-oss-120b"),
    ("groq", "qwen/qwen3.8-27b"),
)


def attempt_sequence() -> list[tuple[str, str]]:
    """Ordered (provider, model) attempts for test generation.

    Derived from the test_generator agent's declared model configs so the
    retry ladder follows the same routing the role advertises; falls back
    to DEFAULT_ATTEMPT_SEQUENCE when the registry is unpopulated.
    """
    try:
        from app.agents.registry import agent_registry

        agent = agent_registry.get_agent("test_generator")
        if agent is not None:
            declared = [
                (cfg.provider, cfg.model)
                for cfg in agent.models
                if getattr(cfg, "provider", None) and getattr(cfg, "model", None)
            ]
            deduped = list(dict.fromkeys(declared))
            if deduped:
                return deduped
    except Exception:  # noqa: BLE001 - the static ladder is a safe fallback
        pass
    return list(DEFAULT_ATTEMPT_SEQUENCE)


class TestGenerationRequest(BaseModel):
    code: str = Field(..., max_length=64000, description="Complete source code to test; oversized requests are rejected, never silently truncated")
    file_type: str = Field(default="python", description="Language of source code")
    test_framework: Literal["pytest", "unittest", "jest", "playwright"] = Field(
        default="pytest", description="Testing framework target"
    )
    project_goal: str = Field(default="", max_length=4000)
    requirements: list[str] = Field(default_factory=list)
    coverage_targets: list[str] = Field(
        default_factory=list, description="Target functions, classes, or edge cases to cover"
    )


class TestGenerationResponse(BaseModel):
    test_code: str
    test_strategy: str
    coverage_estimate: float | None = None
    generation_status: Literal["generated", "invalid_output", "degraded"] = "generated"
    error: str | None = None
    latency_ms: float
    # TASK-REL-026: attempt accounting so a caller can tell a first-try
    # success from a recovered one, and a no-tests outcome carries an
    # explicit retryable signal instead of looking like a 200 success.
    attempts: int = 1
    provider_used: str | None = None
    model_used: str | None = None
    retryable: bool = False


class TestGenerationService:
    """Generates comprehensive unit, edge case, and fixture-backed automated test suites."""

    @staticmethod
    def _validate_suite(test_text: str, req: TestGenerationRequest) -> str | None:
        """Return None when the extracted text is a usable suite, else the
        invalid_output reason (the pre-REL-026 checks, unchanged)."""
        if not test_text.strip():
            return "empty_test_output"
        if req.file_type == "python":
            try:
                tree = ast.parse(test_text)
                tests = [node for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and node.name.startswith("test_")]
                if not tests:
                    raise ValueError("No test functions or methods were generated.")
                if req.test_framework == "unittest" and not any(
                    isinstance(node, ast.ClassDef) and any(
                        isinstance(base, ast.Name) and base.id == "TestCase"
                        or isinstance(base, ast.Attribute) and base.attr == "TestCase"
                        for base in node.bases)
                    for node in ast.walk(tree)
                ):
                    raise ValueError("Requested unittest.TestCase suite was not generated.")
            except (SyntaxError, ValueError) as exc:
                return type(exc).__name__
        return None

    async def _run_attempt(
        self, req: TestGenerationRequest, prompt: str, provider: str, model: str
    ) -> tuple[str, str | None, str | None]:
        """One generation attempt against one declared provider/model.

        Returns (outcome, test_text, detail): outcome is "generated",
        "degraded" (provider unreachable/timed out) or "invalid_output"
        (provider answered but produced no usable suite).
        """
        exec_req = UnifiedExecutionRequest(
            provider=provider,
            model=model,
            agent_role="test_generator",
            prompt=prompt,
            max_tokens=8000,
            temperature=0.2
        )
        try:
            exec_res = await asyncio.wait_for(
                unified_provider_manager.execute(exec_req),
                timeout=ATTEMPT_TIMEOUT_SECONDS,
            )
        except (asyncio.TimeoutError, TimeoutError):
            return (
                "degraded",
                None,
                f"{provider}: attempt exceeded {ATTEMPT_TIMEOUT_SECONDS:.0f}s",
            )
        except Exception as exc:  # noqa: BLE001 - one attempt must never kill the request
            return "degraded", None, f"{provider}: {type(exc).__name__}"

        if exec_res.degraded:
            return "degraded", None, exec_res.error or f"{provider}: provider degraded"

        test_text = extract_code(exec_res.content or "", req.file_type)
        invalid_reason = self._validate_suite(test_text, req)
        if invalid_reason is not None:
            return "invalid_output", None, invalid_reason
        return "generated", test_text, None

    async def generate_tests(self, req: TestGenerationRequest) -> TestGenerationResponse:
        start_time = time.perf_counter()

        module_guidance = ("Import the supplied implementation as main, do not invent a different module name. "
                           if req.file_type == "python" else "Use the supplied implementation and project module conventions. ")
        prompt = (
            f"Generate an exhaustive test suite using `{req.test_framework}` for the following `{req.file_type}` code:\n\n"
            f"```\n{req.code}\n```\n\n"
            f"Original project objective: {req.project_goal}\n"
            f"Required behavior: {req.requirements}\n"
            f"Coverage Targets: {', '.join(req.coverage_targets) if req.coverage_targets else 'All public functions and edge cases'}\n\n"
            "Include: (1) Happy path tests, (2) Boundary condition and error tests, (3) Mocking/fixtures where required. "
            "Test the requested behavior, not merely the implementation's current behavior. "
            f"{module_guidance}"
            "Do not copy/reimplement the application into the tests. "
            "Return only complete runnable test source, no narration."
        )

        sequence = attempt_sequence()
        failures: list[tuple[str, str, str, str]] = []  # (outcome, provider, model, detail)
        attempts_made = 0
        for provider, model in sequence:
            attempts_made += 1
            outcome, test_text, detail = await self._run_attempt(req, prompt, provider, model)
            if outcome == "generated":
                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                if attempts_made > 1:
                    logger.info(
                        "Test generation recovered on attempt %d/%d via %s/%s after %s",
                        attempts_made, len(sequence), provider, model,
                        "; ".join(f"{p}/{m}: {d}" for _, p, m, d in failures),
                    )
                return TestGenerationResponse(
                    test_code=test_text or "",
                    test_strategy=f"Generated {req.test_framework} suite; not executed, coverage not measured.",
                    coverage_estimate=None,
                    generation_status="generated",
                    latency_ms=elapsed_ms,
                    attempts=attempts_made,
                    provider_used=provider,
                    model_used=model,
                )
            failures.append((outcome, provider, model, detail or outcome))
            logger.warning(
                "Test generation attempt %d/%d via %s/%s produced no suite (%s: %s)",
                attempts_made, len(sequence), provider, model, outcome, detail,
            )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        summary = "; ".join(
            f"attempt {i} ({p}/{m}): {d}" for i, (_, p, m, d) in enumerate(failures, 1)
        )
        # The terminal status describes the final attempt's failure kind:
        # models answered but none produced a usable suite (invalid_output),
        # or no model could be reached in time (degraded). Both mean "no
        # tests" and both are retryable; the router maps them to 503.
        final_outcome = failures[-1][0] if failures else "degraded"
        if final_outcome == "invalid_output":
            return TestGenerationResponse(
                test_code="", test_strategy="No usable test suite generated.",
                generation_status="invalid_output", error=summary, latency_ms=elapsed_ms,
                attempts=attempts_made, retryable=True,
            )
        return TestGenerationResponse(
            test_code="", test_strategy="No tests generated: provider unavailable.",
            generation_status="degraded", error=summary, latency_ms=elapsed_ms,
            attempts=attempts_made, retryable=True,
        )


test_generation_service = TestGenerationService()

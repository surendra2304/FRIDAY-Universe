"""Automated Test Generation Service for FORGE."""

import ast
import time
from typing import Literal

from pydantic import BaseModel, Field

from app.services.code_generation import extract_code

from app.providers.unified_manager import (
    UnifiedExecutionRequest,
    unified_provider_manager,
)


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


class TestGenerationService:
    """Generates comprehensive unit, edge case, and fixture-backed automated test suites."""

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

        exec_req = UnifiedExecutionRequest(
            provider="auto",
            agent_role="test_generator",
            prompt=prompt,
            max_tokens=8000,
            temperature=0.2
        )

        exec_res = await unified_provider_manager.execute(exec_req)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        if exec_res.degraded:
            return TestGenerationResponse(
                test_code="", test_strategy="No tests generated: provider unavailable.",
                generation_status="degraded", error=exec_res.error, latency_ms=elapsed_ms,
            )

        test_text = extract_code(exec_res.content or "")
        if not test_text.strip():
            return TestGenerationResponse(
                test_code="", test_strategy="No test source generated.",
                generation_status="invalid_output", error="empty_test_output", latency_ms=elapsed_ms,
            )
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
                return TestGenerationResponse(
                    test_code="", test_strategy="No usable Python test suite generated.",
                    generation_status="invalid_output", error=type(exc).__name__, latency_ms=elapsed_ms,
                )

        return TestGenerationResponse(
            test_code=test_text,
            test_strategy=f"Generated {req.test_framework} suite; not executed, coverage not measured.",
            coverage_estimate=None,
            generation_status="generated",
            latency_ms=elapsed_ms,
        )


test_generation_service = TestGenerationService()

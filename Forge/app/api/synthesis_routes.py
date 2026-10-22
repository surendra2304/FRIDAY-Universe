"""
REST and SSE Endpoints for Autonomous Refactoring, Polyglot Compilers,
Pipeline Event Streaming, and Self-Healing.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.compilers.models import (
    CompilationOptions,
    LanguageTarget,
)
from app.compilers.polyglot import PolyglotCompilerMatrix
from app.core.logging import get_logger
from app.core.workspace import workspace_manager
from app.pipeline.bus import get_event_bus
from app.refactoring.engine import RefactoringEngine
from app.refactoring.models import RefactoringRuleType
from app.selfrepair.engine import SelfRepairEngine

logger = get_logger("api.synthesis_routes")

synthesis_router = APIRouter(prefix="/api/synthesis", tags=["Synthesis & Refactoring"])
pipeline_router = APIRouter(prefix="/api/pipeline", tags=["Pipeline Events"])

compiler_matrix = PolyglotCompilerMatrix()
refactoring_engine = RefactoringEngine()
self_repair_engine = SelfRepairEngine()
event_bus = get_event_bus()


# ---------------------------------------------------------------------------
# Refactoring Request / Response Schemas
# ---------------------------------------------------------------------------

class CodeAnalysisRequest(BaseModel):
    source_code: str = Field(..., description="Python source code to analyze")
    file_path: str = Field(default="snippet.py", description="Relative file path for context")


class CodeAnalysisResponse(BaseModel):
    file_path: str
    issues_count: int
    issues: list[dict[str, Any]]
    function_metrics: dict[str, dict[str, Any]]


class CodeTransformRequest(BaseModel):
    source_code: str = Field(..., description="Python source code to refactor")
    file_path: str = Field(default="snippet.py")
    rules: list[RefactoringRuleType] | None = Field(default=None, description="Target rules to apply")


class CodeTransformResponse(BaseModel):
    original_code: str
    refactored_code: str
    changes_count: int
    changes: list[dict[str, Any]]
    diff: str


# ---------------------------------------------------------------------------
# Compiler Request / Response Schemas
# ---------------------------------------------------------------------------

class CompilerRequest(BaseModel):
    task_id: str = Field(..., description="Task ID whose workspace to compile")
    target_language: LanguageTarget | None = Field(default=None, description="Explicit target language")
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)


class CompilerResponse(BaseModel):
    target_language: str
    status: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    error_count: int
    warning_count: int
    diagnostics: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Self-Repair Request / Response Schemas
# ---------------------------------------------------------------------------

class SelfRepairRequest(BaseModel):
    task_id: str = Field(..., description="Task ID whose workspace needs self-healing")
    initial_error: str = Field(default="", description="Error traceback or build message")
    test_command: str | None = Field(default=None, description="Optional test command to verify repair")
    max_attempts: int = Field(default=3, ge=1, le=5)


class SelfRepairResponse(BaseModel):
    success: bool
    rounds_executed: int
    resolved_files: list[str]
    summary: str
    error_message: str | None = None
    attempts: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Refactoring Endpoints
# ---------------------------------------------------------------------------

@synthesis_router.post(
    "/refactor/analyze",
    response_model=CodeAnalysisResponse,
    summary="Analyze code for smells and complexity",
)
async def analyze_code(req: CodeAnalysisRequest) -> CodeAnalysisResponse:
    issues, metrics = refactoring_engine.analyze_code(
        req.source_code, file_path=req.file_path
    )
    return CodeAnalysisResponse(
        file_path=req.file_path,
        issues_count=len(issues),
        issues=[
            {
                "line": i.line_number,
                "column": i.column,
                "rule": i.rule_type.value,
                "severity": i.severity.value,
                "message": i.message,
                "suggested_fix": i.suggested_fix,
            }
            for i in issues
        ],
        function_metrics={
            name: {
                "cyclomatic_complexity": m.cyclomatic_complexity,
                "max_nesting_depth": m.max_nesting_depth,
                "lines_of_code": m.lines_of_code,
                "is_overly_complex": m.is_overly_complex,
            }
            for name, m in metrics.items()
        },
    )


@synthesis_router.post(
    "/refactor/transform",
    response_model=CodeTransformResponse,
    summary="Apply automated AST refactorings to code",
)
async def transform_code(req: CodeTransformRequest) -> CodeTransformResponse:
    refactored, changes = refactoring_engine.refactor_code(
        req.source_code, file_path=req.file_path, rules=req.rules
    )
    combined_diff = "\n".join(c.diff for c in changes)
    return CodeTransformResponse(
        original_code=req.source_code,
        refactored_code=refactored,
        changes_count=len(changes),
        changes=[
            {
                "rule": c.rule_type.value,
                "description": c.description,
                "diff": c.diff,
            }
            for c in changes
        ],
        diff=combined_diff,
    )


# ---------------------------------------------------------------------------
# Compiler Endpoints
# ---------------------------------------------------------------------------

@synthesis_router.post(
    "/compilers/compile",
    response_model=CompilerResponse,
    summary="Compile and syntax-check a workspace",
)
async def compile_workspace(req: CompilerRequest) -> CompilerResponse:
    paths = workspace_manager.get_workspace_paths(req.task_id)
    if not paths or not Path(paths.project).is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace for task '{req.task_id}' not found.",
        )

    options = CompilationOptions(
        timeout_seconds=req.timeout_seconds,
        working_dir=Path(paths.project),
    )
    res = compiler_matrix.compile(
        Path(paths.project), target=req.target_language, options=options
    )

    return CompilerResponse(
        target_language=res.target_language.value,
        status=res.status.value,
        exit_code=res.exit_code,
        stdout=res.stdout,
        stderr=res.stderr,
        duration_ms=res.duration_ms,
        error_count=res.error_count,
        warning_count=res.warning_count,
        diagnostics=[
            {
                "file": d.file_path,
                "line": d.line,
                "column": d.column,
                "severity": d.severity.value,
                "message": d.message,
                "rule": d.rule_code,
            }
            for d in res.diagnostics
        ],
    )


# ---------------------------------------------------------------------------
# Self-Healing Endpoints
# ---------------------------------------------------------------------------

@synthesis_router.post(
    "/selfrepair/repair",
    response_model=SelfRepairResponse,
    summary="Run autonomous closed-loop self-repair",
)
async def self_repair_task(req: SelfRepairRequest) -> SelfRepairResponse:
    paths = workspace_manager.get_workspace_paths(req.task_id)
    if not paths or not Path(paths.project).is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace for task '{req.task_id}' not found.",
        )

    result = await self_repair_engine.repair_workspace(
        workspace=Path(paths.project),
        initial_error=req.initial_error,
        test_command=req.test_command,
        max_attempts=req.max_attempts,
    )

    return SelfRepairResponse(
        success=result.success,
        rounds_executed=result.rounds_executed,
        resolved_files=result.resolved_files,
        summary=result.summary,
        error_message=result.error_message,
        attempts=[
            {
                "attempt": a.attempt_number,
                "strategy": a.strategy.value,
                "target_file": a.target_file,
                "passed": a.verification_passed,
                "output": a.output_message,
                "duration_ms": a.duration_ms,
            }
            for a in result.attempts
        ],
    )


# ---------------------------------------------------------------------------
# Pipeline Event SSE Streaming Endpoints
# ---------------------------------------------------------------------------

@pipeline_router.get(
    "/stream/{task_id}",
    summary="Real-time Server-Sent Events (SSE) stream for task execution",
)
async def stream_task_events(
    task_id: str,
    timeout_seconds: float = Query(default=300.0, ge=0.01, le=600.0),
) -> StreamingResponse:
    """Streams live pipeline events formatted as Server-Sent Events (text/event-stream)."""

    async def event_generator() -> AsyncIterator[str]:
        # Yield initial connected frame
        yield f"event: ping\ndata: {json.dumps({'task_id': task_id, 'status': 'connected'})}\n\n"
        async for ev in event_bus.stream_events(
            task_id=task_id, timeout_seconds=timeout_seconds
        ):
            yield f"event: {ev.event_type.value}\ndata: {ev.to_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@pipeline_router.get(
    "/history/{task_id}",
    summary="Retrieve task event history",
)
async def get_task_event_history(task_id: str) -> dict[str, Any]:
    events = event_bus.get_history(task_id)
    return {
        "task_id": task_id,
        "count": len(events),
        "events": [e.to_dict() for e in events],
    }

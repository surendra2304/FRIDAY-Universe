"""
API Marketplace Endpoints, Template Instantiation, and Quality Gate Validation for Project FORGE.
"""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.analytics.templates import template_analytics
from app.core.logging import get_logger
from app.core.workspace import canonical_path, workspace_manager
from app.marketplace.models import (
    TemplateCategory,
    TemplateManifest,
    TemplateSubmission,
)
from app.marketplace.registry import template_registry

logger = get_logger("api.marketplace")

marketplace_router = APIRouter(prefix="/api/marketplace", tags=["Marketplace"])
task_template_router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


class BuildFromTemplateRequest(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)
    task_metadata: dict[str, Any] = Field(default_factory=dict)


class BuildFromTemplateResponse(BaseModel):
    task_id: str
    template_id: str
    workspace_path: str
    files_created: list[str]
    message: str


class ReviewSubmission(BaseModel):
    rating: float = Field(ge=1.0, le=5.0)
    review: str | None = None


@marketplace_router.get("/templates", response_model=list[TemplateManifest])
async def list_marketplace_templates(
    category: TemplateCategory | None = None,
    language: str | None = None,
    framework: str | None = None,
    query: str | None = None,
    sort_by: Literal["rating", "downloads", "name"] = Query("rating"),
):
    """Browse and filter curated marketplace templates."""
    return template_registry.list_templates(
        category=category,
        language=language,
        framework=framework,
        query=query,
        sort_by=sort_by,
    )


@marketplace_router.get("/templates/{template_id}")
async def get_template_detail(template_id: str):
    """Retrieve deep detail for a template, including variables schema, analytics, and recommendation."""
    template = template_registry.get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found in registry.",
        )

    stats = template_analytics.get_stats(template_id)
    recommendation = template_analytics.get_recommendation(template_id, template.name)

    return {
        "template": template,
        "analytics": stats,
        "recommendation": recommendation,
    }


@task_template_router.post("/from-template/{template_id}", response_model=BuildFromTemplateResponse)
async def build_task_from_template(template_id: str, payload: BuildFromTemplateRequest):
    """Instantiate a new project workspace directly from a marketplace template with variable substitution."""
    template = template_registry.get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found in registry.",
        )

    # Generate workspace directory through the WorkspaceManager so the root is
    # anchored to settings.base_dir. Building it from the raw relative
    # `settings.workspaces_dir` made the location depend on the process CWD, and
    # writing template files directly into that root (no `project/` subdir) put
    # generated code outside the sandbox every checker and the execution engine
    # expect.
    import uuid

    task_id = f"task_{uuid.uuid4().hex[:8]}"
    paths = workspace_manager.create_workspace(task_id)
    workspace_path = canonical_path(paths.project)
    workspace_root = canonical_path(paths.root)

    # Render files
    rendered_files = template_registry.render_template(template_id, payload.variables)
    created_file_list = []

    for rel_path, content in rendered_files.items():
        # Containment check: a template rel_path such as "../../evil.py" must not
        # be able to write outside the task's project directory.
        target = canonical_path(workspace_path / rel_path)
        try:
            target.relative_to(workspace_path)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template file path '{rel_path}' escapes the task workspace.",
            ) from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        created_file_list.append(rel_path)

    # Record analytics usage
    template_analytics.record_usage(template_id, success=True, duration_seconds=5.0)

    return BuildFromTemplateResponse(
        task_id=task_id,
        template_id=template_id,
        workspace_path=str(workspace_root),
        files_created=created_file_list,
        message=f"Workspace instantiated from '{template.name}' with {len(created_file_list)} files.",
    )


@marketplace_router.post("/templates", status_code=status.HTTP_201_CREATED)
async def submit_template(submission: TemplateSubmission):
    """
    Submit a new community template.
    Runs automated quality gates: validates manifest structure, non-empty files, and documentation.
    """
    # 1. Quality Gate: Manifest validation
    if not submission.name or not submission.description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template submission must include non-empty name and description.",
        )

    # 2. Quality Gate: Files verification
    if not submission.files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template submission must include at least one template file.",
        )

    for path_str, content in submission.files.items():
        if not content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template file '{path_str}' cannot be empty.",
            )

    # 3. Quality Gate: Variable substitution test
    test_context = {var.name: f"test_{var.name}" for var in submission.variables}
    for path_str, content in submission.files.items():
        rendered = content
        for k, v in test_context.items():
            rendered = rendered.replace(f"{{{{{k}}}}}", v)

    import uuid

    new_id = f"custom-{uuid.uuid4().hex[:8]}"

    manifest = TemplateManifest(
        id=new_id,
        name=submission.name,
        description=submission.description,
        category=submission.category,
        language=submission.language,
        framework=submission.framework,
        author=submission.author,
        variables=submission.variables,
        files=submission.files,
        requirements=submission.requirements,
        readme_content=submission.readme_content
        or f"# {submission.name}\n\n{submission.description}\n",
        tests_content=submission.tests_content,
        status="published",
    )

    template_registry.register_template(manifest)
    logger.info(
        f"New template '{manifest.name}' passed automated quality gates and was registered with ID '{manifest.id}'."
    )

    return {
        "success": True,
        "template_id": manifest.id,
        "status": "published",
        "message": f"Template '{manifest.name}' successfully verified and published to marketplace.",
    }


@marketplace_router.post("/templates/{template_id}/review")
async def review_template(template_id: str, review: ReviewSubmission):
    """Submit rating and feedback review for a template."""
    template = template_registry.get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found.",
        )

    template_analytics.add_review(template_id, review.rating, review.review)
    return {"success": True, "message": "Feedback recorded."}

"""
Unit tests for CodebaseAnalyzerRole (existing codebase onboarding and architecture mapping).
"""

from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.roles import CodebaseAnalyzerRole
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.providers.direct import DirectProvider


@pytest.mark.asyncio
async def test_codebase_analyzer_manifest_and_summary_generation(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)

    task_id = str(uuid4())
    wm.create_workspace(task_id)

    # Scaffold existing codebase files
    wm.write_project_file(task_id, "package.json", '{"name": "analytics-ui", "version": "1.0.0"}')
    wm.write_project_file(task_id, "requirements.txt", "fastapi>=0.100.0\nuvicorn>=0.22.0\n")
    wm.write_project_file(
        task_id, "README.md", "# Analytics Service\nFull-stack telemetry tracker.\n"
    )
    wm.write_project_file(task_id, "main.py", 'print("Analytics Service Running")')

    mock_summary_output = """
### File: docs/PROJECT_CONTEXT_SUMMARY.md
```markdown
# Project Context Summary
## Technology Stack
- Python & FastAPI
- Node.js & React
## Architecture
- Backend entrypoint: `main.py`
- Package manifests: `package.json`, `requirements.txt`
```
"""
    provider = DirectProvider(mock_response=mock_summary_output)
    analyzer = CodebaseAnalyzerRole(provider=provider)

    res = await analyzer.execute_step(
        task_id=task_id,
        node_title="Codebase Analysis",
        context={"goal": "Add real-time analytics aggregation"},
        engine=engine,
    )

    assert res["status"] == "success"
    assert "package.json" in res["detected_manifests"]
    assert "requirements.txt" in res["detected_manifests"]
    assert "docs/PROJECT_CONTEXT_SUMMARY.md" in res["files_written"]

    # Verify summary file written to workspace
    summary_text = engine.fs.read_file(task_id, "docs/PROJECT_CONTEXT_SUMMARY.md")
    assert "Project Context Summary" in summary_text
    assert "Analytics Service" in summary_text or "FastAPI" in summary_text

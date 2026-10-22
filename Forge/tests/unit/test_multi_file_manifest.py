"""
Unit tests for File Manifest generation and Multi-File Project Synthesis via AI Universe.
"""

import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.agents.roles import ArchitectRole, DeveloperRole
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.integrations.ai_universe_client import AIUniverseResponse
from app.verification.checkers import BuildChecker, LintChecker


@pytest.fixture
def temp_engine(tmp_path: Path):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    return engine, wm


@pytest.mark.asyncio
async def test_architect_generates_file_manifest(temp_engine):
    """Validates that ArchitectRole generates docs/FILE_MANIFEST.json for website prompt."""
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    architect = ArchitectRole()

    context = {"goal": "Build a modern responsive portfolio website"}
    result = await architect.execute_step(
        task_id=task_id,
        node_title="System Architecture & Module Design",
        context=context,
        engine=engine,
    )

    assert result["status"] == "success"
    assert "docs/FILE_MANIFEST.json" in result["files_written"]
    assert isinstance(result["file_manifest"], list)
    assert len(result["file_manifest"]) >= 2
    assert "index.html" in result["file_manifest"]
    assert "style.css" in result["file_manifest"]

    # Verify on disk
    manifest_raw = engine.fs.read_file(task_id, "docs/FILE_MANIFEST.json", role="architect")
    manifest_data = json.loads(manifest_raw)
    assert "index.html" in manifest_data


@pytest.mark.asyncio
async def test_developer_generates_multiple_distinct_files_from_manifest(temp_engine):
    """
    Validates that DeveloperRole iterates through the File Manifest, calls AI Universe
    for each distinct file, and saves all files (index.html, style.css, app.js) to the workspace.
    """
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole()

    # Define simulated AI Universe responses for each file
    responses_by_file = {
        "index.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Portfolio</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>Welcome to My Portfolio</h1>
    <div id="content">Loading projects...</div>
    <script src="app.js"></script>
</body>
</html>""",
        "style.css": """body {
    font-family: sans-serif;
    margin: 0;
    padding: 20px;
    background-color: #f4f4f4;
}
h1 {
    color: #333;
}""",
        "app.js": """document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById('content');
    if (el) {
        el.textContent = 'Projects loaded successfully.';
    }
});""",
    }

    async def mock_ask_impl(question: str, mode: str = "auto"):
        for filename, content in responses_by_file.items():
            if filename in question:
                return AIUniverseResponse(
                    answer=content,
                    confidence=0.95,
                    run_id=f"run_manifest_{filename}",
                )
        return AIUniverseResponse(answer="/* generic */", confidence=0.85, run_id="run_fallback")

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask", side_effect=mock_ask_impl
    ) as mock_ask:
        context = {
            "goal": "Build a responsive web application",
            "file_manifest": ["index.html", "style.css", "app.js"],
        }

        result = await developer.execute_step(
            task_id=task_id,
            node_title="Implement Web Application",
            context=context,
            engine=engine,
        )

        assert result["status"] == "success"
        assert "index.html" in result["files_written"]
        assert "style.css" in result["files_written"]
        assert "app.js" in result["files_written"]

        # Verify AI Universe was called for each file
        assert mock_ask.call_count == 3

        # Verify content written to disk
        html_on_disk = engine.fs.read_file(task_id, "index.html", role="developer")
        assert "Welcome to My Portfolio" in html_on_disk

        css_on_disk = engine.fs.read_file(task_id, "style.css", role="developer")
        assert "background-color: #f4f4f4" in css_on_disk

        js_on_disk = engine.fs.read_file(task_id, "app.js", role="developer")
        assert "Projects loaded successfully" in js_on_disk


@pytest.mark.asyncio
async def test_verification_battery_handles_multi_file_web_assets(temp_engine):
    """Validates that BuildChecker and LintChecker parse and validate HTML/CSS/JS files."""
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    # Write clean web assets
    engine.fs.create_file(
        task_id=task_id,
        relative_path="index.html",
        content="<!DOCTYPE html><html><head><title>App</title></head><body><h1>Hello</h1></body></html>",
        role="developer",
    )
    engine.fs.create_file(
        task_id=task_id,
        relative_path="style.css",
        content="body { margin: 0; padding: 10px; }",
        role="developer",
    )
    engine.fs.create_file(
        task_id=task_id,
        relative_path="app.js",
        content="console.log('App running');",
        role="developer",
    )

    build_checker = BuildChecker()
    build_evidence = await build_checker.run_check(task_id, engine)
    assert build_evidence.passed is True
    assert "index.html" in build_evidence.artifacts_inspected

    lint_checker = LintChecker()
    lint_evidence = await lint_checker.run_check(task_id, engine)
    assert lint_evidence.passed is True
    assert "HTML / Web Static Linter" in lint_evidence.check_name

"""
Golden Benchmark 3: Static HTML/CSS/JS Web Application.
Validates end-to-end autonomous synthesis of frontend web projects with BrowserChecker and screenshot evidence.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.execution.delivery import DeliveryPackager
from app.execution.engine import ExecutionEngine
from app.integrations.ai_universe_client import AIUniverseResponse
from app.memory.db import DatabaseManager
from app.memory.models import TaskMode, TaskState
from app.memory.state_store import StateStore
from app.verification.checkers import BrowserChecker


@pytest.mark.asyncio
async def test_golden_benchmark_static_web_application(temp_dir: Path):
    """
    Benchmark Scenario: Build an interactive Portfolio & Landing Page with HTML, CSS, JavaScript,
    and verify page layout, asset resolution, and visual screenshot generation.
    """
    # 1. Environment Setup
    db_mgr = DatabaseManager(db_path=temp_dir / "golden_web.db")
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    orchestrator = OrchestratorCore(store=store, wm=wm, engine=engine)

    goal = "Create a responsive interactive landing page in HTML5, CSS3, and modern JavaScript"
    requirements = [
        "Include responsive header, hero section, and interactive feature cards",
        "Add interactive dark mode toggle in JavaScript",
        "Verify 100% asset resolution and capture visual screenshot evidence",
    ]

    # 2. Intake and Planning
    task, _ = await orchestrator.intake_and_plan(
        goal=goal,
        requirements=requirements,
        mode=TaskMode.AUTONOMOUS,
    )
    task_id = task.id
    assert task.state == TaskState.READY

    # 3. Scaffold Implementation in Workspace
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Forge Portfolio & Landing Page</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header class="navbar">
        <div class="logo">FORGE Engine</div>
        <button id="theme-btn" class="btn">Toggle Theme</button>
    </header>
    <main class="hero">
        <h1>Autonomous Software Synthesis</h1>
        <p>From high-level specification to verified production artifacts.</p>
        <div id="status-card" class="card">
            <h3>System Status</h3>
            <p id="status-text">Operational</p>
        </div>
    </main>
    <script src="app.js"></script>
</body>
</html>
"""

    css_content = """/* Responsive styles for FORGE landing page */
:root {
    --bg-color: #0f172a;
    --text-color: #f8fafc;
    --primary: #38bdf8;
    --card-bg: #1e293b;
}

body.light {
    --bg-color: #ffffff;
    --text-color: #0f172a;
    --primary: #0284c7;
    --card-bg: #f1f5f9;
}

body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: var(--bg-color);
    color: var(--text-color);
    transition: background-color 0.3s ease;
}

.navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem 2rem;
}

.logo {
    font-weight: bold;
    font-size: 1.25rem;
    color: var(--primary);
}

.btn {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    border: none;
    background: var(--primary);
    color: #ffffff;
    cursor: pointer;
}

.hero {
    text-align: center;
    padding: 4rem 2rem;
}

.card {
    background: var(--card-bg);
    border-radius: 8px;
    padding: 2rem;
    max-width: 400px;
    margin: 2rem auto;
}
"""

    js_content = """// Interactive theme and state handler
document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("theme-btn");
    const statusText = document.getElementById("status-text");

    if (btn) {
        btn.addEventListener("click", () => {
            document.body.classList.toggle("light");
            if (statusText) {
                statusText.innerText = document.body.classList.contains("light") ? "Light Mode Active" : "Dark Mode Active";
            }
        });
    }
});
"""

    responses = {
        "index.html": html_content,
        "style.css": css_content,
        "app.js": js_content,
        "README.md": "# Static Web Application\n",
    }

    async def mock_ask_impl(question: str, mode: str = "auto"):
        for fname, code in responses.items():
            if fname in question:
                return AIUniverseResponse(answer=code, confidence=0.95, run_id=f"run_{fname}")
        return AIUniverseResponse(answer=html_content, confidence=0.95, run_id="run_default")

    # 4. Autonomous DAG Execution
    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask", side_effect=mock_ask_impl
    ):
        task = await orchestrator.run_task(task_id, max_iterations=10)
        assert task.state == TaskState.COMPLETED

    # 5. Browser Verification
    browser_checker = BrowserChecker()
    evidence = await browser_checker.run_check(task_id, engine)
    assert evidence.passed is True
    assert evidence.exit_code == 0

    # 6. Delivery Packaging
    packager = DeliveryPackager(engine=engine, wm=wm)
    delivery = await packager.package_delivery(
        task_id=task_id,
        goal=goal,
        requirements=requirements,
        stack="HTML5 / CSS3 / JavaScript",
        tag_name="v1.0-forge-delivery",
    )

    assert delivery.release_tag == "v1.0-forge-delivery"
    assert len(delivery.browser_verification_evidence) >= 1

    # 7. Assert artifacts exist
    artifacts_dir = wm.get_task_workspace_dir(task_id) / "artifacts"
    assert (artifacts_dir / "completion_report.json").exists()
    assert (artifacts_dir / "COMPLETION_REPORT.md").exists()
    # Browser evidence must be real. This golden benchmark used to assert a
    # hardcoded 1x1 PNG that BrowserChecker wrote and called a "screenshot".
    # The assertion now demands the honest contract: the fetched HTML is
    # persisted and the metadata records that no screenshot was captured.
    evidence_files = list(artifacts_dir.glob("browser_evidence_*.html"))
    assert len(evidence_files) >= 1
    assert evidence_files[0].stat().st_size > 0
    meta_files = list(artifacts_dir.glob("browser_evidence_*.meta.json"))
    assert len(meta_files) >= 1
    import json as _json

    _meta = _json.loads(meta_files[0].read_text(encoding="utf-8"))
    assert _meta["screenshot"] is False
    assert not list(artifacts_dir.glob("screenshot_*.png")), (
        "BrowserChecker still fabricates a 1x1 PNG as screenshot evidence"
    )

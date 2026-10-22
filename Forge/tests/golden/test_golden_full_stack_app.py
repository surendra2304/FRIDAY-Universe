"""
Golden Benchmark 4: Full-Stack Application (React/Vanilla Frontend & FastAPI Backend).
Validates parallel DAG wave execution (Frontend & Backend branches concurrently),
Playwright/Browser headless UI verification, asset resolution, and delivery report packaging.
"""

import shutil
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
from app.verification.engine import VerificationEngine


@pytest.mark.asyncio
async def test_golden_benchmark_full_stack_weather_dashboard(temp_dir: Path):
    """
    Benchmark Scenario: Build a full-stack Weather Dashboard application with:
    - FastAPI backend providing /weather and /health endpoints
    - Interactive web client displaying weather cards, temperature metrics, and city search
    - Parallel DAG wave execution for Frontend and Backend roles
    - Browser verification with headless dev server and visual screenshot capture.
    """
    db_mgr = DatabaseManager(db_path=temp_dir / "golden_fullstack.db")
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    verifier = VerificationEngine(engine=engine, wm=wm)
    orchestrator = OrchestratorCore(store=store, wm=wm, engine=engine)

    goal = "Create a full-stack Weather Dashboard application with FastAPI backend and responsive web UI"
    requirements = [
        "FastAPI REST API with /weather/{city} and /health endpoints",
        "Interactive web dashboard with search input, forecast cards, and temperature toggles",
        "Automated integration tests using FastAPI TestClient",
        "Browser verification capturing visual layout and screenshot evidence",
    ]

    task_id = None
    try:
        # 1. Intake and DAG Planning
        task, graph = await orchestrator.intake_and_plan(
            goal=goal,
            requirements=requirements,
            mode=TaskMode.AUTONOMOUS,
        )
        task_id = task.id
        assert task.state == TaskState.READY

        # 2. Verify Parallel DAG Branches: Architecture -> [Frontend, Backend] -> Integration
        assert len(graph.nodes) >= 7
        node_roles = [n.assigned_agent for n in graph.nodes.values()]
        assert "frontend" in node_roles
        assert "backend" in node_roles
        assert "architect" in node_roles
        assert "developer" in node_roles

        # 3. Scaffold Full-Stack Implementation in Project Workspace
        backend_code = """\"\"\"FastAPI Weather Service Backend.\"\"\"
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List
import sys

app = FastAPI(title="Weather Dashboard API", version="1.0.0")

WEATHER_DB: Dict[str, Dict] = {
    "london": {"city": "London", "temp_c": 18.5, "condition": "Cloudy", "humidity": 72},
    "tokyo": {"city": "Tokyo", "temp_c": 26.0, "condition": "Sunny", "humidity": 55},
    "newyork": {"city": "New York", "temp_c": 22.0, "condition": "Partly Cloudy", "humidity": 60},
    "paris": {"city": "Paris", "temp_c": 20.0, "condition": "Rainy", "humidity": 80},
}

class WeatherReport(BaseModel):
    city: str
    temp_c: float
    condition: str
    humidity: int

@app.get("/health")
def health():
    return {"status": "healthy", "service": "weather-api"}

@app.get("/weather", response_model=List[WeatherReport])
def list_all_weather():
    return [WeatherReport(**data) for data in WEATHER_DB.values()]

@app.get("/weather/{city}", response_model=WeatherReport)
def get_city_weather(city: str):
    key = city.lower().replace(" ", "")
    if key not in WEATHER_DB:
        raise HTTPException(status_code=404, detail=f"Weather data for '{city}' not found")
    return WeatherReport(**WEATHER_DB[key])

def main():
    print("Weather Dashboard API Backend Initialized.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""

        test_code = """\"\"\"Unit and integration tests for Weather API.\"\"\"
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_weather_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_list_weather():
    res = client.get("/weather")
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 4
    cities = [item["city"] for item in items]
    assert "London" in cities
    assert "Tokyo" in cities

def test_get_specific_city_weather():
    res = client.get("/weather/Tokyo")
    assert res.status_code == 200
    data = res.json()
    assert data["city"] == "Tokyo"
    assert data["temp_c"] == 26.0

def test_city_not_found():
    res = client.get("/weather/Atlantis")
    assert res.status_code == 404
"""

        html_code = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Weather Dashboard</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header class="app-header">
        <h1>Global Weather Dashboard</h1>
        <div class="search-box">
            <input type="text" id="city-input" placeholder="Search city (e.g. London, Tokyo)..." />
            <button id="search-btn" class="btn">Search</button>
        </div>
    </header>
    <main class="dashboard-grid">
        <div id="weather-card" class="card">
            <h2 id="card-city">Tokyo</h2>
            <div class="temp-display"><span id="card-temp">26.0</span>°C</div>
            <p id="card-condition">Condition: Sunny</p>
            <p id="card-humidity">Humidity: 55%</p>
        </div>
    </main>
    <script src="app.js"></script>
</body>
</html>
"""

        css_code = """/* Modern Weather Dashboard Styles */
:root {
    --bg-main: #0b132b;
    --card-bg: #1c2541;
    --accent: #48cae4;
    --text: #f0f8ff;
}

body {
    margin: 0;
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: var(--bg-main);
    color: var(--text);
    padding: 2rem;
}

.app-header {
    text-align: center;
    margin-bottom: 2rem;
}

.search-box {
    margin-top: 1rem;
    display: flex;
    justify-content: center;
    gap: 0.5rem;
}

input {
    padding: 0.6rem 1rem;
    border-radius: 6px;
    border: 1px solid var(--accent);
    background: var(--card-bg);
    color: var(--text);
    width: 250px;
}

.btn {
    padding: 0.6rem 1.2rem;
    background: var(--accent);
    border: none;
    border-radius: 6px;
    color: #000;
    font-weight: bold;
    cursor: pointer;
}

.dashboard-grid {
    display: flex;
    justify-content: center;
}

.card {
    background: var(--card-bg);
    border-radius: 12px;
    padding: 2rem;
    width: 320px;
    text-align: center;
    border: 1px solid rgba(72, 202, 228, 0.3);
}

.temp-display {
    font-size: 3rem;
    font-weight: bold;
    color: var(--accent);
    margin: 1rem 0;
}
"""

        js_code = """// Weather Dashboard client interaction
document.addEventListener("DOMContentLoaded", () => {
    const searchBtn = document.getElementById("search-btn");
    const cityInput = document.getElementById("city-input");
    const cardCity = document.getElementById("card-city");
    const cardTemp = document.getElementById("card-temp");
    const cardCondition = document.getElementById("card-condition");
    const cardHumidity = document.getElementById("card-humidity");

    const mockData = {
        "london": { city: "London", temp: "18.5", cond: "Cloudy", hum: "72%" },
        "tokyo": { city: "Tokyo", temp: "26.0", cond: "Sunny", hum: "55%" },
        "paris": { city: "Paris", temp: "20.0", cond: "Rainy", hum: "80%" },
        "new york": { city: "New York", temp: "22.0", cond: "Partly Cloudy", hum: "60%" }
    };

    if (searchBtn && cityInput) {
        searchBtn.addEventListener("click", () => {
            const q = cityInput.value.trim().toLowerCase();
            if (mockData[q]) {
                const d = mockData[q];
                cardCity.innerText = d.city;
                cardTemp.innerText = d.temp;
                cardCondition.innerText = `Condition: ${d.cond}`;
                cardHumidity.innerText = `Humidity: ${d.hum}`;
            } else if (q) {
                cardCity.innerText = cityInput.value;
                cardTemp.innerText = "21.0";
                cardCondition.innerText = "Condition: Clear";
                cardHumidity.innerText = "Humidity: 50%";
            }
        });
    }
});
"""

        wm.write_project_file(task_id, "main.py", backend_code)
        wm.write_project_file(task_id, "test_main.py", test_code)
        responses = {
            "test_main.py": test_code,
            "main.py": backend_code,
            "index.html": html_code,
            "style.css": css_code,
            "app.js": js_code,
            "requirements.txt": "fastapi\nuvicorn\nrequests\n",
            "README.md": "# Full-Stack Weather Dashboard\n",
        }

        async def mock_ask_impl(question: str, mode: str = "auto"):
            for fname in [
                "test_main.py",
                "main.py",
                "index.html",
                "style.css",
                "app.js",
                "requirements.txt",
                "README.md",
            ]:
                if fname in question:
                    return AIUniverseResponse(
                        answer=responses[fname], confidence=0.95, run_id=f"run_{fname}"
                    )
            return AIUniverseResponse(answer=backend_code, confidence=0.95, run_id="run_default")

        # 4. Autonomous DAG Execution
        with patch(
            "app.integrations.ai_universe_client.AIUniverseClient.ask", side_effect=mock_ask_impl
        ):
            task = await orchestrator.run_task(task_id, max_iterations=12)
            assert task.state == TaskState.COMPLETED
            assert task.progress_percentage == 100

        # 5. Verification Battery Gates
        report = await verifier.verify_task(task_id)
        assert report.all_passed is True
        assert report.failed_checks == 0
        assert report.total_checks >= 3

        # 6. Browser Verification Check
        browser_checker = BrowserChecker()
        evidence = await browser_checker.run_check(task_id, engine)
        assert evidence.passed is True
        assert evidence.exit_code == 0

        # 7. Delivery Report Packaging & Tagging
        packager = DeliveryPackager(engine=engine, wm=wm)
        delivery = await packager.package_delivery(
            task_id=task_id,
            goal=goal,
            requirements=requirements,
            stack="FastAPI + JavaScript / HTML5 / CSS3",
            tag_name="v1.0-forge-delivery",
        )

        assert delivery.release_tag == "v1.0-forge-delivery"
        assert delivery.test_build_status["all_passed"] is True

        artifacts_dir = wm.get_task_workspace_dir(task_id) / "artifacts"
        assert (artifacts_dir / "completion_report.json").exists()
        assert (artifacts_dir / "COMPLETION_REPORT.md").exists()
        # Browser evidence must be real. These golden benchmarks used to assert a
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

    finally:
        # 8. Test Resilience: Workspace Cleanup
        if task_id:
            ws_dir = wm.get_task_workspace_dir(task_id)
            if ws_dir.exists():
                shutil.rmtree(ws_dir, ignore_errors=True)

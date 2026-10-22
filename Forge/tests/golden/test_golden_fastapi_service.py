"""
Golden Benchmark 2: FastAPI REST API with SQLite Persistence.
Validates end-to-end autonomous synthesis of backend REST APIs with database models and integration tests.
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
from app.verification.engine import VerificationEngine


@pytest.mark.asyncio
async def test_golden_benchmark_fastapi_sqlite_service(temp_dir: Path):
    """
    Benchmark Scenario: Build a FastAPI Expense Tracker REST API with SQLite database and CRUD tests.
    """
    # 1. Environment Setup
    db_mgr = DatabaseManager(db_path=temp_dir / "golden_api.db")
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    verifier = VerificationEngine(engine=engine, wm=wm)
    orchestrator = OrchestratorCore(store=store, wm=wm, engine=engine)

    goal = "Create a FastAPI Expense Tracker REST API with SQLite database and CRUD endpoints"
    requirements = [
        "POST /expenses (create an expense with description, amount, category)",
        "GET /expenses (list all expenses)",
        "GET /expenses/{id} (retrieve a specific expense)",
        "Automated integration tests using FastAPI TestClient",
    ]

    task_id = None
    try:
        # 2. Intake and Planning
        task, _graph = await orchestrator.intake_and_plan(
            goal=goal,
            requirements=requirements,
            mode=TaskMode.AUTONOMOUS,
        )
        task_id = task.id
        assert task.state == TaskState.READY

        # 3. Scaffold Implementation in Workspace
        app_code = """\"\"\"FastAPI Expense Tracker Application.\"\"\"
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import sqlite3
from typing import List
import sys

app = FastAPI(title="Expense Tracker API", version="1.0.0")
DB_PATH = "expenses.db"

def init_sqlite():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(\"\"\"
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL
        )
    \"\"\")
    conn.commit()
    conn.close()

init_sqlite()

class ExpenseCreate(BaseModel):
    description: str
    amount: float = Field(gt=0)
    category: str = "General"

class ExpenseResponse(BaseModel):
    id: int
    description: str
    amount: float
    category: str

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(item: ExpenseCreate):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO expenses (description, amount, category) VALUES (?, ?, ?)",
                (item.description, item.amount, item.category))
    conn.commit()
    exp_id = cur.lastrowid
    conn.close()
    return ExpenseResponse(id=exp_id, description=item.description, amount=item.amount, category=item.category)

@app.get("/expenses", response_model=List[ExpenseResponse])
def list_expenses():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, description, amount, category FROM expenses")
    rows = cur.fetchall()
    conn.close()
    return [ExpenseResponse(id=r[0], description=r[1], amount=r[2], category=r[3]) for r in rows]

@app.get("/expenses/{exp_id}", response_model=ExpenseResponse)
def get_expense(exp_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, description, amount, category FROM expenses WHERE id = ?", (exp_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Expense not found")
    return ExpenseResponse(id=row[0], description=row[1], amount=row[2], category=row[3])

def main():
    print("FastAPI Expense Tracker Service Initialized.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""

        test_code = """\"\"\"Integration tests for Expense Tracker API.\"\"\"
from fastapi.testclient import TestClient
from main import app, init_sqlite

client = TestClient(app)

def setup_module():
    init_sqlite()

def test_expense_crud_lifecycle():
    # 1. Health
    h_res = client.get("/health")
    assert h_res.status_code == 200
    assert h_res.json()["status"] == "healthy"

    # 2. Create
    payload = {"description": "Server hosting", "amount": 49.99, "category": "Cloud"}
    c_res = client.post("/expenses", json=payload)
    assert c_res.status_code == 201
    created = c_res.json()
    assert created["id"] is not None
    assert created["description"] == "Server hosting"
    exp_id = created["id"]

    # 3. Get by ID
    g_res = client.get(f"/expenses/{exp_id}")
    assert g_res.status_code == 200
    assert g_res.json()["amount"] == 49.99

    # 4. List
    l_res = client.get("/expenses")
    assert l_res.status_code == 200
    items = l_res.json()
    assert len(items) >= 1
"""

        wm.write_project_file(task_id, "main.py", app_code)
        responses = {
            "test_main.py": test_code,
            "main.py": app_code,
            "README.md": "# Expense Tracker API\n",
        }

        async def mock_ask_impl(question: str, mode: str = "auto"):
            for fname in ["test_main.py", "main.py", "README.md"]:
                if fname in question:
                    return AIUniverseResponse(
                        answer=responses[fname], confidence=0.95, run_id=f"run_{fname}"
                    )
            return AIUniverseResponse(answer=app_code, confidence=0.95, run_id="run_default")

        # 4. Autonomous DAG Execution
        with patch(
            "app.integrations.ai_universe_client.AIUniverseClient.ask", side_effect=mock_ask_impl
        ):
            task = await orchestrator.run_task(task_id, max_iterations=10)
            assert task.state == TaskState.COMPLETED

        # 5. Verification Battery
        report = await verifier.verify_task(task_id)
        if not report.all_passed:
            print("FASTAPI FAIL REASONS:", report.failure_reasons)
            for ev in report.evidence:
                print("EV:", ev.check_name, ev.passed, "ERR:", ev.stderr, "OUT:", ev.stdout)
        assert report.all_passed is True
        assert report.failed_checks == 0

        # 6. Delivery Packaging
        packager = DeliveryPackager(engine=engine, wm=wm)
        delivery = await packager.package_delivery(
            task_id=task_id,
            goal=goal,
            requirements=requirements,
            stack="Python / FastAPI / SQLite",
            tag_name="v1.0-forge-delivery",
        )

        assert delivery.release_tag == "v1.0-forge-delivery"
        assert delivery.stack == "Python / FastAPI / SQLite"

        # 7. Verification Artifacts
        artifacts_dir = wm.get_task_workspace_dir(task_id) / "artifacts"
        assert (artifacts_dir / "completion_report.json").exists()
        assert (artifacts_dir / "COMPLETION_REPORT.md").exists()
    finally:
        if task_id:
            import shutil

            ws_dir = wm.get_task_workspace_dir(task_id)
            if ws_dir.exists():
                shutil.rmtree(ws_dir, ignore_errors=True)

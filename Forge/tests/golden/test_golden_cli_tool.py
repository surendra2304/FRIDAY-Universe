"""
Golden Benchmark 1: Python CLI Todo Application.
Validates end-to-end autonomous synthesis, execution, verification, and delivery report generation.
"""

import json
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
async def test_golden_benchmark_python_cli_tool(temp_dir: Path):
    """
    Benchmark Scenario: Build a clean CLI Todo utility with JSON persistence and unit tests.
    """
    # 1. Environment Setup
    db_mgr = DatabaseManager(db_path=temp_dir / "golden_cli.db")
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    verifier = VerificationEngine(engine=engine, wm=wm)
    orchestrator = OrchestratorCore(store=store, wm=wm, engine=engine)

    goal = "Create a robust Python CLI Todo application with JSON persistence"
    requirements = [
        "Support adding, listing, completing, and deleting todos",
        "Include unit tests with 100% assertion coverage",
        "Provide CLI argument parsing via argparse",
    ]

    task_id = None
    try:
        # 2. Intake and DAG Planning
        task, graph = await orchestrator.intake_and_plan(
            goal=goal,
            requirements=requirements,
            mode=TaskMode.AUTONOMOUS,
        )
        task_id = task.id
        assert task.state == TaskState.READY
        assert len(graph.nodes) >= 6

        # 3. Scaffold Implementation in Workspace
        cli_code = """\"\"\"CLI Todo Application.\"\"\"
import argparse
import json
from pathlib import Path
import sys

TODO_FILE = Path("todos.json")

def load_todos():
    if not TODO_FILE.exists():
        return []
    try:
        return json.loads(TODO_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_todos(todos):
    TODO_FILE.write_text(json.dumps(todos, indent=2), encoding="utf-8")

def add_todo(title):
    todos = load_todos()
    todo_id = len(todos) + 1
    todos.append({"id": todo_id, "title": title, "done": False})
    save_todos(todos)
    return todo_id

def list_todos():
    return load_todos()

def complete_todo(todo_id):
    todos = load_todos()
    for t in todos:
        if t["id"] == todo_id:
            t["done"] = True
            save_todos(todos)
            return True
    return False

def main():
    parser = argparse.ArgumentParser(description="CLI Todo Manager")
    subparsers = parser.add_subparsers(dest="command")

    add_p = subparsers.add_parser("add")
    add_p.add_argument("title", type=str)

    subparsers.add_parser("list")

    comp_p = subparsers.add_parser("complete")
    comp_p.add_argument("id", type=int)

    args = parser.parse_args()
    if args.command == "add":
        tid = add_todo(args.title)
        print(f"Added todo #{tid}")
        return 0
    elif args.command == "list":
        for t in list_todos():
            status = "[x]" if t["done"] else "[ ]"
            print(f"{t['id']}. {status} {t['title']}")
        return 0
    elif args.command == "complete":
        if complete_todo(args.id):
            print(f"Completed todo #{args.id}")
            return 0
        print("Todo not found")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""

        test_code = """\"\"\"Unit tests for CLI Todo application.\"\"\"
from main import add_todo, list_todos, complete_todo

def test_todo_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr("main.TODO_FILE", tmp_path / "todos.json")

    # 1. Add
    tid = add_todo("Buy groceries")
    assert tid == 1

    # 2. List
    todos = list_todos()
    assert len(todos) == 1
    assert todos[0]["title"] == "Buy groceries"
    assert todos[0]["done"] is False

    # 3. Complete
    res = complete_todo(1)
    assert res is True
    updated = list_todos()
    assert updated[0]["done"] is True
"""

        wm.write_project_file(task_id, "main.py", cli_code)
        wm.write_project_file(task_id, "test_main.py", test_code)
        responses = {
            "test_main.py": test_code,
            "main.py": cli_code,
            "README.md": "# CLI Todo Application\n",
        }

        async def mock_ask_impl(question: str, mode: str = "auto"):
            for fname in ["test_main.py", "main.py", "README.md"]:
                if fname in question:
                    return AIUniverseResponse(
                        answer=responses[fname], confidence=0.95, run_id=f"run_{fname}"
                    )
            return AIUniverseResponse(answer=cli_code, confidence=0.95, run_id="run_default")

        # 4. Execute TaskGraph
        with patch(
            "app.integrations.ai_universe_client.AIUniverseClient.ask", side_effect=mock_ask_impl
        ):
            task = await orchestrator.run_task(task_id, max_iterations=10)
            assert task.state == TaskState.COMPLETED
            assert task.progress_percentage == 100

        # 5. Verification Battery Gates
        report = await verifier.verify_task(task_id)
        if not report.all_passed:
            print("FAIL REASONS:", report.failure_reasons)
            for ev in report.evidence:
                print("EV:", ev.check_name, ev.passed, "ERR:", ev.stderr, "OUT:", ev.stdout)
        assert report.all_passed is True
        assert report.failed_checks == 0
        assert report.total_checks >= 3

        # 6. Delivery Packaging & Tagging
        packager = DeliveryPackager(engine=engine, wm=wm)
        delivery = await packager.package_delivery(
            task_id=task_id,
            goal=goal,
            requirements=requirements,
            tag_name="v1.0-forge-delivery",
        )

        assert delivery.release_tag == "v1.0-forge-delivery"
        assert delivery.test_build_status["all_passed"] is True

        # 7. Assert artifacts exist
        artifacts_dir = wm.get_task_workspace_dir(task_id) / "artifacts"
        assert (artifacts_dir / "completion_report.json").exists()
        assert (artifacts_dir / "COMPLETION_REPORT.md").exists()
        assert (artifacts_dir / "verification_report.json").exists()

        report_json = json.loads(
            (artifacts_dir / "completion_report.json").read_text(encoding="utf-8")
        )
        assert report_json["objective"] == goal
        assert len(report_json["requirements"]) == 3
        assert report_json["release_tag"] == "v1.0-forge-delivery"
    finally:
        if task_id:
            import shutil

            ws_dir = wm.get_task_workspace_dir(task_id)
            if ws_dir.exists():
                shutil.rmtree(ws_dir, ignore_errors=True)
